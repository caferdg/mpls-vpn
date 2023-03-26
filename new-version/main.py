import json, os, sys, gns3fy, time, telnetlib
from structures import *

# TO DO
# - MP BGP
# - BGP VRF

if len(sys.argv) != 3:
    print("Usage: python3 main.py <intentFile> <projectName>")
    exit(1)

# Import GNS Project
projectName = sys.argv[2]
serv = gns3fy.Gns3Connector("http://localhost:3080")
project = gns3fy.Project(name=projectName, connector=serv)
project.get()
gnsLinks = project.links_summary(is_print=False)
gnsRouters = project.nodes_summary(is_print=False)

# Import Intent File
f = open(sys.argv[1], "r")
jsonFile = json.load(f)
f.close()
pref = jsonFile["preferences"]
vrfList = jsonFile["vrf"]

# Create routers list
routers = []
counter = 0
for router in gnsRouters:
    counter += 1
    routers.append(Router(router[0], router[2], counter, 0, []))
nbRouter = len(routers)

def getRouter(name):
    for router in routers:
        if router.name == name:
            return router
    return None

# Fill adjList for each router
for link in gnsLinks:
    getRouter(link[0]).adjList.append(Adj(link[1], getRouter(link[2]), ""))
    getRouter(link[2]).adjList.append(Adj(link[3], getRouter(link[0]), ""))

# Create AS list
asList = []
for asNum, content in jsonFile["as"].items():
    newAs = AS(asNum, content["name"], [], content["prefix"], [])
    asList.append(newAs)
    for router in routers:
        if router.name in content["routers"]:
            router.As = newAs
            asList[-1].routerList.append(router)
nbAs = len(asList)


def getSubnet(As):
    for subnet in As.subList:
        if subnet.taken == False:
            subnet.taken = True
            return subnet
    return None

def freeSubnet(As, subnet):
    for sub in As.subList:
        if sub.num == subnet:
            sub.taken = False
            return
    return None

def assignIP():
    for router in routers:
        for adj in router.adjList:
            if adj.ip == "":
                subnet = getSubnet(router.As)
                adj.ip = f"{router.As.prefix}{subnet.num}.1"
                for neighAdj in adj.neighbor.adjList:
                    if neighAdj.neighbor == router:
                        neighAdj.ip = f"{router.As.prefix}{subnet.num}.2"
                        break
assignIP()

def telWrite(tel, strin):
    tel.write(strin.encode())
    time.sleep(0.05)
    tel.write(b"\r")

# START
for router in routers:
    tel = telnetlib.Telnet("localhost", router.port)
    telWrite(tel, "")
    time.sleep(0.1)
    telWrite(tel, "end")
    telWrite(tel, "enable")
    telWrite(tel, "conf t")
    tel.close()

# VRF
for vrf in vrfList:
    for PE in vrf["PE"]:
        edgeRouter = getRouter(PE["name"])
        tel = telnetlib.Telnet("localhost", edgeRouter.port)
        # DEFINITIONS
        telWrite(tel, "vrf definition " + vrf["name"])
        telWrite(tel, "rd " + PE["rd"])
        telWrite(tel, "route-target export " + PE["rt-export"])
        telWrite(tel, "route-target import " + PE["rt-import"])
        telWrite(tel, "address-family ipv4")
        telWrite(tel, "exit-address-family")
        telWrite(tel, "exit")
        # FORWARDING
        for adj in edgeRouter.adjList:
            if adj.neighbor.As != edgeRouter.As:
                telWrite(tel, "interface " + adj.interface)
                telWrite(tel, "vrf forwarding " + vrf["name"])
                telWrite(tel, "exit")
        tel.close()


# INTERFACES IP ADDRESS
for router in routers:
    tel = telnetlib.Telnet("localhost", router.port)
    for adj in router.adjList:
        telWrite(tel, "interface " + adj.interface)
        telWrite(tel, "ip address " + adj.ip + " 255.255.255.0")
        telWrite(tel, "no shutdown")
        telWrite(tel, "exit")
    tel.close()

# OSPF
for router in routers:
    tel = telnetlib.Telnet("localhost", router.port)
    telWrite(tel, "router ospf 1")
    telWrite(tel, f"router-id {router.id}.{router.id}.{router.id}.{router.id}")
    telWrite(tel, "exit")
    for adj in router.adjList:
        if adj.neighbor.As == router.As:
            telWrite(tel, "interface " + adj.interface)
            telWrite(tel, "ip ospf 1 area 0")
            telWrite(tel, "exit")
    tel.close()

# LOOPBACKS
for router in routers:
    tel = telnetlib.Telnet("localhost", router.port)
    telWrite(tel, "interface loopback 0")
    telWrite(tel, "ip address " + pref["lp-prefix"] + str(router.id) + " 255.255.255.255")
    telWrite(tel, "no shutdown")
    telWrite(tel, "ip ospf 1 area 0")
    telWrite(tel, "exit")
    tel.close()

# MPLS
for router in routers:
    if router.As.name == "provider":
        tel = telnetlib.Telnet("localhost", router.port)
        for adj in router.adjList:
            if adj.neighbor.As == router.As:
                telWrite(tel, "interface " + adj.interface)
                telWrite(tel, "mpls ip")
                telWrite(tel, "exit")
        tel.close()

for router in routers:
    tel = telnetlib.Telnet("localhost", router.port)
    telWrite(tel, "end")
    telWrite(tel, "write")
    time.sleep(0.1)
    telWrite(tel, "")
    tel.close()
