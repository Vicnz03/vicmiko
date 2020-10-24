# vicmiko
Python library  to interact with Junos devices. Based on jnpr-pyez and jsnapy.

## Install
```
pip install vicmiko
```

## Feature supported
1.  junos_get: get from junos box, support pipe
2.  junos_compare: show diffs of config
3.  junos_commit: commit config to box
4.  jsnapy_pre
5.  jsnapy_post
6.  jsnapy_check
7.  junos_rpc
8.  junos_view
9.  junos_ping
10. junos_traceroute
11. junos_commit_file
12. junos_compare_file
13. junos_install

## Example
```
from vicmiko.junos import JunOSDriver
from vicmiko import junos

jnpr = JunOSDriver(hostname='192.168.0.1',username="admin",password="admin")
jnpr.open()

jnpr.junos_get(['show version'])
jnpr.junos_rpc('get-software-information')
jnpr.junos_rpc('get-software-information',to_str=0)
jnpr.junos_compare(['set interfaces ge-0/0/0 description "to SRX300 port 01"'])
jnpr.load_junos_view('view.yml')
mem = junos.junos_routing_engine_table(jnpr.device) 
jnpr.jsnapy_pre(['test_memory.yml'])
jnpr.junos_commit(mode='exclusive', commands=['set interfaces ge-0/0/0 description "to SRX300 port 00"'], commit_comments='vicmiko test')
jnpr.junos_ping(host= '111.69.2.29')
jnpr.junos_traceroute(host= '111.69.2.29')
jnpr.junos_scp(mode='put',local = 'test.txt', remote = '/var/tmp/')
jnpr.junos_scp(mode='get',local = '.', remote = '/var/tmp/test.txt')
```
