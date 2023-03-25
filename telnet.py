import json, os, sys, telnetlib, time

if len(sys.argv) != 3:
    print("Usage: python3 telnet.py <intentFile> <outputDir>")
    exit(1)
    
# IMPORT NETWORK INTENT
intent = sys.argv[1]
outputPath = sys.argv[2]
f = open(intent, "r")
jsonFile = json.load(f)
f.close()
routers = jsonFile["routers"]
autoSys = jsonFile["as"]
nbRouter = len(routers)
nbAs = len(autoSys)


# PREFERENCES
lpPrefix = jsonFile["preferences"]["lp-prefix"] # must be a /112 !!
ripName = jsonFile["preferences"]["ripName"]
ospfProcess = str(jsonFile["preferences"]["ospfPid"])
customPref = jsonFile["preferences"]["custom-pref"]
peerPref = jsonFile["preferences"]["peer-pref"]
providerPref = jsonFile["preferences"]["provider-pref"]
vrf = jsonFile["preferences"]["vrf"]

asInf = dict() # dictionnary containing the ip prefix and the index of each AS
for i in range(nbAs):
    as_ = autoSys[i]
    asInf[as_["id"]] = dict(prefix = as_["ip-prefix"], index = i)

matAdj = [] # Matrice contenant les numeros des sous-reseaux entre chaque routeur, (matrice symetrique)
for k in range(0,nbRouter):
    matAdj.append([])
    for j in range(nbRouter):
        matAdj[k].append(0)

listeSousRes = [] # Liste contenant les compteurs sous-reseaux utilises pour chaque AS
for k in range(0,nbAs):
    listeSousRes.append(0)

matAdjAs = [] # Matrice contenant les prefixes des sous-reseaux entre chaque AS, (matrice symetrique)
for k in range(0,nbAs):
    matAdjAs.append([])
    for j in range(nbAs):
        matAdjAs[k].append("")

def getASBRlist(asId):
    res = []
    for router in routers:
        if router["as"] == asId:
            for adj in router["adj"]:
                for link in adj["links"]:
                    if link["protocol-type"] == "egp" and router["id"] not in res:
                        res.append(router["id"])
    return res


for router in routers:
    name = router["name"]
    id = router["id"]
    tn = telnetlib.Telnet("localhost", 5000 + id-1)
    As = router["as"]
    igp = [a["igp"] for a in autoSys if a["id"]==As][0]
    egp = [a["egp"] for a in autoSys if a["id"]==As][0]
    asType = [a["type"] for a in autoSys if a["id"]==As][0]
    adj = router["adj"]
    egpNeigbors = []
    ASBRlist = getASBRlist(As)
    isASBR = id in ASBRlist

    def telWrite(strin):
        tn.write(str.encode(strin))
        time.sleep(0.01)

    # CONSTANTS
    telWrite("enable\r")
    telWrite("conf t\r")
    telWrite(f"version 15.2\rservice timestamps debug datetime msec\rservice timestamps log datetime msec\r!\rhostname {name}\r!\rboot-start-marker\rboot-end-marker\rno aaa new-model\rno ip icmp rate-limit unreachable\rip cef\rno ip domain lookup\rno ipv6 cef\rmultilink bundle-name authenticated\rip tcp synwait-time 5\r!\r")

    # VRF definitions
    if asType == "provider" and isASBR:
        for customer in vrf:
            name=customer["name"]
            rd = customer["rd"]
            rt = customer["rt"]
            telWrite(f"vrf definition {name}\r")
            telWrite(f"rd {rd}\r")
            telWrite("route-target export {rt}\r")
            telWrite("route-target import {rt}\r")
            telWrite("address-family ipv4\r")
            telWrite("exit-address-family\r!\r")
            telWrite("exit\r")

    ## LOOPBACK INTERFACE
    telWrite(f"interface Loopback0\r ip address {lpPrefix}{id} 255.255.255.255\r")
    if(igp == "ospf"):
        telWrite(f"ip ospf {ospfProcess} area 0\r")
    telWrite("exit\r")
    
    
    ## PHYSICAL INTERFACES
    for adj in router["adj"]: # this loops fills egpNeigbors (if the router is an ASBR ofc)
        neighbID = adj["neighbor"]
        neighbAs = [router["as"] for router in routers if router["id"]==neighbID][0]
        preferedAs = As # used for choosing the ip prefixes (either As or neighbAs)
        asInd = asInf[As]["index"]
        neighbAsInd = asInf[neighbAs]["index"]

        for link in adj["links"]:

            ## IP GENERATION
            if link["protocol-type"] == "igp": # routeur a l'interieur de l'AS (pas ASBR)telWrite(
                ip = asInf[As]["prefix"]
            if link["protocol-type"] == "egp": # routeur en bordure d'AS
                isASBR = True
                if matAdjAs[asInd][neighbAsInd] == "" and matAdjAs[neighbAsInd][asInd]=="": # adjacence inter AS pas encore initialise
                    ip = asInf[preferedAs]["prefix"]
                    matAdjAs[asInd][neighbAsInd], matAdjAs[neighbAsInd][asInd] = ip, ip
                else : # adjacence inter AS connue
                    ip = matAdjAs[asInd][neighbAsInd]

            if matAdj[id-1][neighbID-1] == 0 and matAdj[neighbID-1][id-1]==0: # sous reseau pas encore initialise
                listeSousRes[asInf[preferedAs]["index"]] += 1
                matAdj[id-1][neighbID-1], matAdj[neighbID-1][id-1] = listeSousRes[asInf[preferedAs]["index"]], listeSousRes[asInf[preferedAs]["index"]]
                ip += str(matAdj[id-1][neighbID-1]) + ".1"
                if isASBR and link["protocol-type"] == "egp":
                    egpNeigbors.append(ip[:-1] + "2" + " " + str(neighbAs))
            else: # sous reseau deja cree
                ip += str(matAdj[id-1][neighbID-1]) + ".2"
                if isASBR and link["protocol-type"] == "egp":
                    egpNeigbors.append(ip[:-1] + "1" + " "+ str(neighbAs))

            # INTERFACE
            telWrite("interface " + link["interface"] + "\r")
            if link["interface"].startswith("FastEthernet") :
                telWrite("duplex full\r")
            if link["interface"].startswith("GigabitEthernet") :
                telWrite("negotiation auto\r")

            if asType == "provider" and link["protocol-type"] == "egp":
                neighborAs = int(egpNeigbors[-1].split()[1])
                neighbAsName = [client["name"] for client in vrf if neighborAs in client["as"]][0]
                telWrite(f"vrf forwarding {neighbAsName}\r")

            telWrite(f"ip address {ip} 255.255.255.0\r")

            if link["protocol-type"] == "igp":
                if asType=="provider":
                    telWrite(f"mpls ip\r")
                if igp == "ospf":
                    telWrite(f"ip ospf {ospfProcess} area 0\r")
                    if "ospf-metric" in link.keys(): # OSPF metric is optional
                        cost = link["ospf-metric"]
                        telWrite(f"ip ospf cost {cost}\r")
            
            telWrite(b"exit\r")

    ## EGP
    if egp == "bgp" and isASBR and asType == "provider":
        telWrite(f"router bgp {As}\r")
        telWrite(f"bgp router-id {id}.{id}.{id}.{id}\r")
        telWrite("bgp log-neighbor-changes\r")

        # iBGP with PE
        for routerID in ASBRlist:
            if routerID != id:
                telWrite(f"neighbor {lpPrefix}{routerID} remote-as {As}\r")
                telWrite(f"neighbor {lpPrefix}{routerID} update-source Loopback0\r")

        telWrite("address-family vpnv4\r")

        for routerID in ASBRlist:
            if routerID != id:
                telWrite(f"neighbor {lpPrefix}{routerID} activate\r")
                telWrite(f"neighbor {lpPrefix}{routerID} send-community both\r")
        telWrite("exit-address-family\r")

        # eBGP with CE
        for customer in vrf:
            custName = customer["name"]
            telWrite(f"address-family ipv4 vrf {custName}\r")
            for extNeighb in egpNeigbors:
                ipNeighb = extNeighb.split()[0]
                asNeighb = int(extNeighb.split()[1])
                if asNeighb in customer["as"]:
                    telWrite(f"neighbor {ipNeighb} remote-as {asNeighb}\r")
                    telWrite(f"neighbor {ipNeighb} activate\r")
            telWrite("exit-address-family\r")
        telWrite("exit\r")
            

    if egp == "bgp" and asType == "customer":
        telWrite(f"router bgp {As}\r")
        telWrite(f"bgp router-id {id}.{id}.{id}.{id}\r")
        telWrite("bgp log-neighbor-changes\r")

        if isASBR :
            for ebgpNeighb in egpNeigbors:
                ipNeighb = ebgpNeighb.split()[0]
                asNeighb = ebgpNeighb.split()[1]
                telWrite(f"neighbor {ipNeighb} remote-as {asNeighb}\r")

        for routerID in [router["id"] for router in routers if router["as"]==As]:
            if routerID != id:
                telWrite(f"neighbor {lpPrefix}{routerID} remote-as {As}\r")
                telWrite(f"neighbor {lpPrefix}{routerID} update-source Loopback0\r")

        telWrite("address-family ipv4\r")

        if isASBR :
            telWrite("redistribute connected\r")
            if(igp == "rip"):
                telWrite(f"redistribute rip {ripName}\r")
            if(igp == "ospf"):
                telWrite(f"redistribute ospf {ospfProcess}\r")
            telWrite("network " + asInf[As]["prefix"] + "0.0\r")
            for ebgpNeighb in egpNeigbors:
                telWrite(f"neighbor {ebgpNeighb.split()[0]} activate\r")
        for routerID in [router["id"] for router in routers if router["as"]==As]:
            if routerID != id:
                telWrite(f"neighbor {lpPrefix}{routerID} activate\r")
        
        telWrite("exit-address-family\r!\r")

    ## IGP
    if(igp == "ospf"):
        telWrite(f"router ospf {ospfProcess}\r router-id {id}.{id}.{id}.{id}\r")
    telWrite("exit\r")
    telWrite("end\r")
    tn.close()

    print(f"Router {id} generated")