from vicmiko.junos import JunOSDriver
from vicmiko import junos

jnpr = JunOSDriver(hostname='192.168.0.1',username="admin",password="admin")
jnpr.open()

jnpr.junos_get(['show version'])
jnpr.junos_rpc('get-software-information')
jnpr.junos_rpc('get-software-information',to_str=0)
jnpr.junos_compare(['set interfaces ge-0/0/0 description "to SRX300 port 01"'])
jnpr.load_junos_view('example/view.yml')
mem = junos.junos_routing_engine_table(jnpr.device) 
jnpr.jsnapy_pre(['example/test_memory.yml'])
jnpr.junos_commit(mode='exclusive', commands=['set interfaces ge-0/0/0 description "to SRX300 port 00"'], commit_comments='vicmiko test')


jnpr.traceroute('111.69.2.29')