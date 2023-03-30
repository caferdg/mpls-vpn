import json, os, sys, gns3fy, time, telnetlib
from structures import *

if len(sys.argv) != 3:
    print("Usage: python3 main.py <intentFile> <projectName>")
    exit(1)

saveName = "previousConf.json"

# Import GNS Project
projectName = sys.argv[2]
serv = gns3fy.Gns3Connector("http://localhost:3080")
project = gns3fy.Project(name=projectName, connector=serv)
project.get()
gnsLinks = project.links_summary(is_print=False)
gnsRouters = project.nodes_summary(is_print=False)

# Import Intent File
with open(sys.argv[1], "r") as f:
    jsonFile = json.load(f)
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

def assignIP():
    for router in routers:
        for adj in router.adjList:
            if adj.ip == "":
                subnet = router.As.getSubnet()
                adj.ip = f"{router.As.prefix}{subnet.num}.1"
                for neighAdj in adj.neighbor.adjList:
                    if neighAdj.neighbor == router:
                        neighAdj.ip = f"{router.As.prefix}{subnet.num}.2"
                        break
assignIP()

# Create Link list
linkList = []
for link in gnsLinks:
    sub = ""
    for adj in getRouter(link[0]).adjList:
        if adj.neighbor.name == link[2]:
            sub = adj.ip[:len(adj.ip)-1]
            break
    linkList.append(Link(getRouter(link[0]), getRouter(link[2]), link[1], link[3], sub))


# SAVE CONFIG
jsonDict = dict(vrfs = [], As = [], links = [])
jsonDict["vrfs"] = vrfList
jsonDict["As"] = [as_.toDict() for as_ in asList]
jsonDict["links"] = [link.toDict() for link in linkList]
with open(saveName, "w") as f:
    json.dump(jsonDict, f, indent=4)

def telWrite(tel, strin):
    tel.write(strin.encode())
    time.sleep(0.02)
    tel.write(b"\r")

# START
for router in routers:
    tel = telnetlib.Telnet("localhost", router.port)
    telWrite(tel, "")
    time.sleep(0.5)
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
            if adj.neighbor.As.name == vrf["name"]:
                telWrite(tel, "interface " + adj.interface)
                telWrite(tel, "vrf forwarding " + vrf["name"])
                telWrite(tel, "exit")
        tel.close()


# INTERFACES' IP ADDRESS
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

# init BGP
for router in routers:
    tel = telnetlib.Telnet("localhost", router.port)
    telWrite(tel, "router bgp " + router.As.id)
    telWrite(tel, f"bgp router-id {router.id}.{router.id}.{router.id}.{router.id}")
    telWrite(tel, "bgp log-neighbor-changes")
    telWrite(tel, "exit")
    tel.close()

# iBGP in customer as
for router in routers:
    if router.As.name != "provider":
        tel = telnetlib.Telnet("localhost", router.port)
        for routerr in router.As.routerList:
            if routerr != router:
                telWrite(tel, "router bgp " + str(router.As.id))
                telWrite(tel, f"neighbor {pref['lp-prefix']}{routerr.id} remote-as {routerr.As.id}")
                telWrite(tel, f"neighbor  {pref['lp-prefix']}{routerr.id} update-source loopback 0")
                telWrite(tel, "address-family ipv4")
                telWrite(tel, f"neighbor {pref['lp-prefix']}{routerr.id} activate")
                telWrite(tel, "exit")
                telWrite(tel, "exit")
        tel.close()

# eBGP
for router in routers:
    if router.isASBR():

        tel = telnetlib.Telnet("localhost", router.port)
        telWrite(tel, "router bgp " + str(router.As.id))

        if router.As.name != "provider":
            telWrite(tel, "address-family ipv4")
            telWrite(tel, f"network {router.As.prefix}0.0")
            telWrite(tel, "redistribute connected")
            telWrite(tel, "redistribute ospf 1")
            for adj in router.adjList:
                if adj.neighbor.As != router.As:
                    telWrite(tel, f"neighbor {adj.getNeighbIp()} remote-as {str(adj.neighbor.As.id)}")
                    telWrite(tel, "address-family ipv4")
                    telWrite(tel, f"neighbor {adj.getNeighbIp()} activate")
                    telWrite(tel, "exit")

        if router.As.name == "provider":
            for adj in router.adjList:
                if adj.neighbor.As != router.As:
                    telWrite(tel, "address-family ipv4 vrf " + adj.neighbor.As.name)
                    telWrite(tel, f"neighbor {adj.getNeighbIp()} remote-as {str(adj.neighbor.As.id)}")
                    telWrite(tel, f"neighbor {adj.getNeighbIp()} activate")
                    telWrite(tel, "exit")
        
        telWrite(tel, "exit")

# MP-BGP between PE's
for As in asList:
    if As.name == "provider":
        for router in As.getASBR():
            tel = telnetlib.Telnet("localhost", router.port)
            telWrite(tel, "router bgp " + str(router.As.id))
            for routerr in As.getASBR():
                if routerr != router:
                    telWrite(tel, f"neighbor {pref['lp-prefix']}{routerr.id} remote-as " + str(As.id))
                    telWrite(tel, f"neighbor {pref['lp-prefix']}{routerr.id} update-source loopback 0")
                    telWrite(tel, "address-family vpnv4")
                    telWrite(tel, f"neighbor {pref['lp-prefix']}{routerr.id} activate")
                    telWrite(tel, f"neighbor {pref['lp-prefix']}{routerr.id} send-community both")
                    telWrite(tel, "exit")
            telWrite(tel, "exit")

for router in routers:
    tel = telnetlib.Telnet("localhost", router.port)
    telWrite(tel, "end")
    telWrite(tel, "write")
    time.sleep(0.1)
    telWrite(tel, "")
    tel.close()