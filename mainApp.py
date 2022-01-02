from netmiko import ConnectHandler
import csv,re,time,threading,optparse
from netmiko.ssh_exception import NetMikoTimeoutException
from netmiko.ssh_exception import NetmikoAuthenticationException
from paramiko.ssh_exception import SSHException
class Shutdown():
    
    def __init__(self):
        self.devices_csv_path = "./devices.csv"
        self.devices = self.get_devices()
        self.options = self.get_options()

        pass
    
    def get_devices(self):
        with open(self.devices_csv_path,"r") as dvc_csv :
            devices_py = csv.DictReader(dvc_csv)
            devices = {}
            for row in devices_py : 
                device_name = row["device"]
                #{'device': 'SW2', 'device_type': 'cisco_ios', 'host': '172.16.1.211', 'username': 'mobo', 'password': 'Pa$$w0rd'}
                del row["device"]
                #{''device_type': 'cisco_ios', 'host': '172.16.1.211', 'username': 'mobo', 'password': 'Pa$$w0rd'}
                
                devices[device_name] = row
                #{'SW2': {'device_type': 'cisco_ios', 'host': '172.16.1.211', 'username': 'mobo', 'password': 'Pa$$w0rd'}, 'SW3':
        return devices
    
    
    def get_options(self):
        parser = optparse.OptionParser()
        parser.add_option('-t','--thread',dest="thread_number",help="for examples if you choose 2, 2 switches will be configured at the same time (its not limit of how many switch you can configure)\nby default its 2\nvalue of 0 is not acceptable.")
        parser.add_option('-m','--mode',dest="mode",help="<strict,vlan> vlan : all interfaces in vlan 1 will be disabled.\nstrict : if the interface didn't receive any traffic it will be disabled.\nby default mode is vlan.")
        options = parser.parse_args()[0]
        return self.options_checker(options,parser)
        
        
        
    def options_checker(self,options,parser):
        #Thread error 
        error = {"number_error" : 0, "message" : ""}
        
        def error_maker(err):
            error["message"] += "\n"+err
            
            error["number_error"] += 1
            
            
        if options.thread_number != None:
            try : 
                options.thread_number = int(options.thread_number)
            except : 
                error_maker("[-] [Error] :the argument for the thread options must be integer . ") 
        else :
            
            options.thread_number = 2
        
        if options.mode != None :
            
            options.mode = options.mode if "vlan" == options.mode or "strict" == options.mode else error_maker("[-] [Error] :Invalid argument. try -h or --help to see valid argument for vlan.")

        # print(options," : ",error["message"])
        # print(error["message"] == "")
        
        if error["number_error"] > 0:
            
            print(f"[+] Error Counter: ",error["number_error"],"\n",error["message"])
            print("[*] [INFORM]: Exiting ...")
            exit()
            
        else :
            return options
        pass
           
        
    def config_connect_devices(self,dvc_name,dvc_value):
        try :
            net_connect = ConnectHandler(**dvc_value)
            net_connect.enable()
            # self.strict_mode(net_connect)
            interfaces = self.vlan_mode(net_connect) if self.options.mode == "vlan" else self.strict_mode(net_connect)

            print(interfaces)
            
            net_connect.config_mode()
            for interface in interfaces : 
                print(f"[+] [{dvc_name}]: shutdown {interface}")
                # time.sleep(0.5)
                out = net_connect.send_command_timing(f"interface {interface}")
                out += net_connect.send_command_timing("shutdown")
        except NetMikoTimeoutException :
            print(f"[-] [Error]: ",dvc_value["host"]," not reachable.")
        except NetmikoAuthenticationException :
            print("[-] [Error]: Authentication Failure.")
        except SSHException :
            print("[-] [Error]: issue with sending ssh request to the target device.")
        except Exception as e :
            print("[-] [Error]: ",e)
                
    
    def the_treader(self):
        #each entry here will represent cleaned version of the output of the command show interfaces stats for each switch. 
        all_threads = []
        for dvc_name,dvc_value in self.devices.items() :
            print(f"[+] [INFORM]: CONNECTING TO {dvc_name}...")
            thread = threading.Thread(target=self.config_connect_devices,args=[dvc_name,dvc_value])
            # thread = self.config_connect_devices(dvc_name,dvc_value)
            
            all_threads.append(thread)
            thread.start()


    
    def strict_mode(self,net_connect):
        # all_switches = []

        output = net_connect.send_command_timing("show interfaces stats")
        data = output.split("\n")
        #each line in this output will represent an entry in the list 
        interface_input = {}
        #in this object will store each interface as a key and its value will be the input traffic value of that interface.
        interface = ""
        
        for line in data :
            if re.search("channel",line) != None or re.search("Vlan",line) != None:
                #we want the check the stats of a physical interface, not a vlan interface or port channel stats.
                #we use break because if the checker reach those type of interface means that we checked all physical interfaces
                #and no need to check further more 
                break
            else : 
                #always the line that contains the interface will be the first one to appear before the line that contains processor. 
                if re.search("Eth",line) != None :
                    # here we are searching in the current line for Eth (Ethernet), and if the checker returned a value not None
                    #we will store the full name of the interface in a variable that we will use as key.
                    #"I Did this just to make sure that there is no whitespace."
                    line = line.split(" ")
                    line = line[0]
                    interface = line
                elif re.search("Processor",line) != None :
                    # the line of the processor contains lot of whitespace so i'm trying to create a list with the delimetter is whitespace.
                    # each whitespace will be an empty entry in the list.
                    input_value = line.split(" ")
                    input_value = list(filter(None,input_value))
                    # then here we are removing the empty entries in the list
                    interface_input[interface] = input_value[1] 
                    #the result will be something like this 
                    #'{Ethernet0/0': '0', 'Ethernet0/2': '0', 'Ethernet0/3': '16210', 'Ethernet3/0': '0', 'Ethernet3/3': '14866'}
        # all_switches.append(interface_input)
        print(interface_input)
        shutdown_interfaces = []
        for interface,inp_v in interface_input.items() : 
            # print(interface,inp_v)
            if inp_v == "0" : 
                shutdown_interfaces.append(interface)
        return shutdown_interfaces
                
                
                
    def vlan_mode(self,net_connect):
        output = net_connect.send_command_timing("show interface status")
        # print(output)
        list_lines = output.split("\n")
        list_lines = list_lines[2::]
        # print(list_lines)
        interfaces_vlan1 = []
        for line in list_lines :
            #here we searching for lines that contains number 1 and between 2 whitespaces
            if re.search(" 1 ",line) != None :
                #Et0/2        connected    1      auto   auto unknown
                only_interface = line.split(" ")
                #Et0/2, , ,    ,,  ,connected ,  , 1 ,   , , auto ,  auto unknown
                only_interface = only_interface[0]
                interfaces_vlan1.append(only_interface)
        return interfaces_vlan1
        
        # for line in list_lines : 
            
        pass
        
        

            
        
            
            
            
            
x = Shutdown()
x.the_treader()
        



