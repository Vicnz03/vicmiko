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

## Example
```
from vicmiko.junos import JunOSDriver
from vicmiko import junos

jnpr = JunOSDriver(hostname='192.168.0.1',username="admin",password="password")
jnpr.open()

jnpr.junos_get(['show version'])
jnpr.junos_rpc('get-software-information')
jnpr.junos_rpc('get-software-information',to_str=0)
jnpr.junos_compare(['set interfaces ge-0/0/0 description "to SRX300 port 01"'])
jnpr.load_junos_view('example/view.yml')
mem = junos.junos_routing_engine_table(jnpr.device) 
jnpr.jsnapy_pre(['example/test_memory.yml'])
jnpr.junos_commit(mode='exclusive', commands=['set interfaces ge-0/0/0 description "to SRX300 port 00"'], commit_comments='vicmiko test')
```
