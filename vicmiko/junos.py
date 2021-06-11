from jnpr.junos import Device
from jnpr.junos.utils.config import Config
from ncclient.operations.rpc import RPCError
from jnpr.junos.exception import ConfigLoadError
from jnpr.junos.exception import RpcTimeoutError
from jnpr.junos.exception import ConnectTimeoutError
from jnpr.junos.exception import ProbeError
from jnpr.junos.exception import LockError as JnprLockError
from jnpr.junos.exception import UnlockError as JnrpUnlockError
from jnpr.jsnapy import SnapAdmin
from jnpr.junos.factory import FactoryLoader
from jnpr.junos.utils.sw import SW
from jnpr.junos.utils.scp import SCP
import xmltodict
import re
import json
import logging
from lxml.builder import E
from lxml import etree
from typing import List
from collections import OrderedDict, defaultdict
import yaml
logger = logging.getLogger(__file__)

class JunOSDriver:
    def __init__(self, hostname, username, password, timeout=60, optional_args={}):
        """
        Initialise JunOS driver.
        Optional args:
            * config_lock (True/False): lock configuration DB after the connection is established.
            * lock_disable (True/False): force configuration lock to be disabled (for external lock
                management).
            * config_private (True/False): juniper configure private command, no DB locking
            * port (int): custom port
            * key_file (string): SSH key file path
            * keepalive (int): Keepalive interval
            * ignore_warning (boolean): not generate warning exceptions
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.timeout = timeout
        self.locked = False

        self.port = optional_args.get("port", 22)
        self.key_file = optional_args.get("key_file", None)
        self.keepalive = optional_args.get("keepalive", 30)
        self.ssh_config_file = optional_args.get("ssh_config_file", None)
        self.ignore_warning = optional_args.get("ignore_warning", False)
        self.auto_probe = optional_args.get("auto_probe", 0)
        self.config_private = optional_args.get("config_private", False)
        self.gather_facts = optional_args.get("gather_facts", False)
        # Junos driver specific options
        self.junos_config_database = optional_args.get(
            "junos_config_database", "committed"
        )

        # config template
        self.jsnapy_test_yml = """  - {}
        """
    
        self.jsnapy_data = """
        hosts:
          - device: {}
            username : {}
            passwd: {}
        tests:
        {}
        sqlite:
          - store_in_sqlite: yes
            check_from_sqlite: yes
            database_name: jsnapy.db  
        """
        if self.key_file:
            self.device = Device(
                hostname,
                user=username,
                password=password,
                ssh_private_key_file=self.key_file,
                ssh_config=self.ssh_config_file,
                port=self.port,
                gather_facts=self.gather_facts,
            )
        else:
            self.device = Device(
                hostname,
                user=username,
                password=password,
                port=self.port,
                ssh_config=self.ssh_config_file,
                gather_facts=self.gather_facts,
            )

        self.platform = "junos"
        self.js = SnapAdmin()

    def open(self):
        """Open the connection with the device."""
        try:
            self.device.open(auto_probe=self.auto_probe)
        except (ConnectTimeoutError, ProbeError) as cte:
            pass
        self.device.timeout = self.timeout
        self.device._conn._session.transport.set_keepalive(self.keepalive)
        if hasattr(self.device, "cu"):
            # make sure to remove the cu attr from previous session
            # ValueError: requested attribute name cu already exists
            del self.device.cu
        self.device.bind(cu=Config)

    def close(self):
        """Close the connection."""
        self.device.close()

    def junos_ping(
        self,
        host,
        source=False,
        ttl=False,
        timeout=False,
        size=False,
        count=False,
        vrf=False,
    ):
        rpc_reply = self.device.rpc.ping(host=host,source = source, ttl=ttl, timeout=timeout, size = size, count = count, vrf = vrf)
        return xmltodict.parse(etree.tostring(rpc_reply))

    def junos_traceroute(
        self,
        host,
        source=False,
        ttl=False,
        timeout=False,
        vrf=False,
        no_resolve=True,
    ):
        rpc_reply = self.device.rpc.traceroute(host=host,source = source, ttl=ttl, timeout=timeout, vrf = vrf, no_resolve=no_resolve)
        return xmltodict.parse(etree.tostring(rpc_reply))

    def junos_get(self, commands: List[str]):
        def _count(txt, none):  # Second arg for consistency only. noqa
            """
            Return the exact output, as Junos displays
            e.g.:
            > show system processes extensive | match root | count
            Count: 113 lines
            """
            count = len(txt.splitlines())
            return "Count: {count} lines".format(count=count)
        
        def _trim(txt, length):
            """
            Trim specified number of columns from start of line.
            """
            try:
                newlines = []
                for line in txt.splitlines():
                    newlines.append(line[int(length) :])
                return "\n".join(newlines)
            except ValueError:
                return txt
        
        def _except(txt, pattern):
            """
            Show only text that does not match a pattern.
            """
            rgx = "^.*({pattern}).*$".format(pattern=pattern)
            unmatched = [
                line for line in txt.splitlines() if not re.search(rgx, line, re.I)
            ]
            return "\n".join(unmatched)
        
        def _last(txt, length):
            """
            Display end of output only.
            """
            try:
                return "\n".join(txt.splitlines()[(-1) * int(length) :])
            except ValueError:
                return txt
        
        def _match(txt, pattern):
            """
            Show only text that matches a pattern.
            """
        
            rgx = '^.*({pattern}).*$'.format(pattern=pattern)
            matched = [line for line in txt.splitlines() if re.search(rgx, line, re.I)]
            return "\n".join(matched)
        
        def _find(txt, pattern):
            """
            Search for first occurrence of pattern.
            """
            rgx = "^.*({pattern})(.*)$".format(pattern=pattern)
            match = re.search(rgx, txt, re.I | re.M | re.DOTALL)
            if match:
                return "{pattern}{rest}".format(pattern=pattern, rest=match.group(2))
            else:
                return "\nPattern not found"
        
        def _process_pipe(cmd, txt):
            """
            Process CLI output from Juniper device that
            doesn't allow piping the output.
            """
            if txt is None:
                return txt
            _OF_MAP = OrderedDict()
            _OF_MAP["except"] = _except
            _OF_MAP["match"] = _match
            _OF_MAP["last"] = _last
            _OF_MAP["trim"] = _trim
            _OF_MAP["count"] = _count
            _OF_MAP["find"] = _find
            # the operations order matter in this case!
            placeholder = 0
            holder = '!will-nerver-use!'
            if '"' in cmd:
                placeholder = 1 
                result = re.search('".*"', cmd, re.I)
                cmd = re.sub('".*"', holder, cmd)
            exploded_cmd = cmd.split("|")
            pipe_oper_args = {}
            for pipe in exploded_cmd[1:]:
                exploded_pipe = pipe.split()
                pipe_oper = exploded_pipe[0]  # always there
                pipe_args = "".join(exploded_pipe[1:2])
                if placeholder and pipe_args == holder:
                    pipe_args = result.group(0).strip('"')
                # will not throw error when there's no arg
                pipe_oper_args[pipe_oper] = pipe_args
            for oper in _OF_MAP.keys():
                # to make sure the operation sequence is correct
                if oper not in pipe_oper_args.keys():
                    continue
                txt = _OF_MAP[oper](txt, pipe_oper_args[oper])
            return txt
        """
        Run commands on remote devices using napalm
        Arguments:
          commands: commands to execute
        Returns:
          Result object with the following attributes set:
            * result (``dict``): result of the commands execution
        """
        result = {}
        cmd_result = ""
        invaild_cmd = re.compile('^(request|clear|start|restart).*')
        get_config = re.compile('^show configuration .*')
        for command in commands:
            if not invaild_cmd.match(command): # if not invaild command predefined
                #(cmd, _, _) = command.partition("|")
                cmds = command.split('|') # split by pipe
                display = '' 
                for item in cmds:
                    if 'display' in item:
                        display = '|' + item # if display in command, store it in display
                try:
                    rsp = self.device.rpc.cli(command=cmds[0]+display, format='text') # rpc call first part of cmd and display, leave the rest for later
                    if rsp is True:
                        cmd_result = ""
                    elif rsp.tag in ["output", "rpc-reply"]:
                        cmd_result= etree.tostring(rsp, method="text", with_tail=False, encoding='unicode')
                    elif rsp.tag == "configuration-information":
                        cmd_result = rsp.findtext("configuration-output")
                    elif rsp.tag == "rpc":
                        return rsp[0]
                    cmd_result = _process_pipe(command,cmd_result)
                except:
                    cmd_result = 'RPC call failed'
                result[command] = cmd_result
            else:
                result[command] = 'Invalid command'

        return result

    def junos_compare(self, commands: List[str] = [''], check = False, format: str='set'):
        diff = ''
        check_result = False
        config_set = '\n'.join(commands)
        with Config(self.device, mode='private') as cu: # config exclusive
            cu.load(config_set, format=format, merge=True) # load config
            diff = cu.diff(0) # show | compare 
            if check:
                check_result = cu.commit_check() # commit check
            cu.rollback()
        
        return {
            'diff': diff,
            'check': check_result,
        }

    def junos_commit(self, mode: str = 'exclusive', commands: List[str] = [''], format: str='set', commit_comments: str = '', comfirm: int = 1):
        config_set = '\n'.join(commands)
        diff = ''
        committed = False
        try:
            with Config(self.device, mode=mode) as cu: # config exclusive
                cu.load(config_set, format=format, merge=True) # load config
                cu.commit_check() # commit check
                diff = cu.diff(0) # show | compare 
                committed = cu.commit(confirm=comfirm, comment=commit_comments) # commit confirm 1 comment
                cu.commit_check() # commit check

        except RPCError as e:
            logger.error(str(e))
            cu.rollback()
            cu.unlock()

        except Exception as e:
            logger.error(str(e))

        return {
            'diff':diff,
            'committed':committed
        }

    def junos_compare_file(self, file_path: str, file_location: str , check = False):
        diff = ''
        check_result = False
        with Config(self.device, mode='private') as cu: # config exclusive
            if file_location == 'local':
                cu.load(path= file_path, merge=True) # load config
            elif file_location == 'remote':
                cu.load(url= file_path, merge=True)
            diff = cu.diff(0) # show | compare 
            if check:
                check_result = cu.commit_check() # commit check
            cu.rollback()
        
        return {
            'diff': diff,
            'check': check_result,
        }

    def junos_commit_file(self, file_path: str, file_location: str, mode: str = 'exclusive', commit_comments: str = '', comfirm: int = 1):
        diff = ''
        committed = False
        try:
            with Config(self.device, mode=mode) as cu: # config exclusive
                if file_location == 'local':
                    cu.load(path= file_path, merge=True) # load config
                elif file_location =='remote':
                    cu.load(url= file_path, merge=True)
                cu.commit_check() # commit check
                diff = cu.diff(0) # show | compare 
                committed = cu.commit(confirm=comfirm, comment=commit_comments) # commit confirm 1 comment
                cu.commit_check() # commit check

        except RPCError as e:
            logger.error(str(e))
            cu.rollback()
            cu.unlock()

        except Exception as e:
            logger.error(str(e))

        return {
            'diff':diff,
            'committed':committed
        }

    def junos_rpc(self,rpc: str, to_str = 1, **kwargs):
        method_to_call = getattr(self.device.rpc, rpc)
        result = method_to_call(**kwargs)
        if to_str:
            result = etree.tostring(result, encoding="unicode", method="text", with_tail=False)
        return result

    def jsnapy_pre(self, jsnapy_test: List[str]):
        # get all check yml and output to file, will use it when post check
        device_test = ''
        for test in jsnapy_test:
            device_test += self.jsnapy_test_yml.format(test)

        # jsnapy pre
        config_host = self.jsnapy_data.format(
            self.hostname, self.username, self.password, device_test)
        snappre = self.js.snap(config_host, "pre")
        '''
        # To_do: nothing to output, maybe get from db from file
        for val in snappre:
            with open(host_pre_result, 'w') as f:
                f.write(json.dumps(dict(val.test_details), indent=4))
        option: get from log
        '''


    def jsnapy_post(self,jsnapy_test: List[str]):
        device_test = ''
        for test in jsnapy_test:
            device_test += self.jsnapy_test_yml.format(test)

        # jsnapy pre
        config_host = self.jsnapy_data.format(
            self.hostname, self.username, self.password, device_test)

        self.js.snap(config_host, "post")
        snapchk = self.js.check(config_host, "pre", "post")
        result = []
        for val in snapchk:
            result.append(dict(val.test_details))

        return result

    def jsnapy_check(self, jsnapy_test: List[str]):
        device_test= ''
        for test in jsnapy_test:
            device_test += self.jsnapy_test_yml.format(test)

        config_host = self.jsnapy_data.format(
            self.hostname, self.username, self.password, device_test)

        snapvalue = self.js.snapcheck(config_host, "snap")
        result = []
        for val in snapvalue:
            result.append(dict(val.test_details))

        return result

    def load_junos_view(self, view_path):
        try:
            with open(view_path) as f:
                tmp_yaml = f.read()
            yaml_str = re.sub(r"unicode", "str", tmp_yaml)
            globals().update(FactoryLoader().load(yaml.safe_load(yaml_str)))
        except:
            pass
    
    def junos_install(self, package, validate=False):
        sw = SW(self.device)
        status, msg = sw.install(package=package, validate=validate, checksum_algorithm='sha256')
        return {
            'status': status,
            'msg': msg,
        }

    def junos_scp(self,mode, local, remote):
        with SCP(self.device, progress=True) as scp:
            if mode == 'put':
                scp.put(local, remote_path=remote)
            elif mode =='get':
                scp.get(remote, local_path=local)