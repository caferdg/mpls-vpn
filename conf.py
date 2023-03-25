import json, os, sys

if len(sys.argv) != 3:
    print("Usage: python3 conf.py <intentFile> <outputDir>")
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
    As = router["as"]
    igp = [a["igp"] for a in autoSys if a["id"]==As][0]
    egp = [a["egp"] for a in autoSys if a["id"]==As][0]
    asType = [a["type"] for a in autoSys if a["id"]==As][0]
    adj = router["adj"]
    egpNeigbors = []
    ASBRlist = getASBRlist(As)
    isASBR = id in ASBRlist

    if not os.path.exists(outputPath):
        os.makedirs(outputPath)
    res = open(f"{outputPath}/i{id}_startup-config.cfg", "w")

    ## CONSTANTS
    res.write(f"version 15.2\nservice timestamps debug datetime msec\nservice timestamps log datetime msec\n!\nhostname {name}\n!\nboot-start-marker\nboot-end-marker\nno aaa new-model\nno ip icmp rate-limit unreachable\nip cef\nno ip domain lookup\nno ipv6 cef\nmultilink bundle-name authenticated\nip tcp synwait-time 5\n!\n")
    res.write("!\n!\n!\n!\n!\n")

    # VRF definitions
    if asType == "provider" and isASBR:
        for customer in vrf:
            name=customer["name"]
            rd = customer["rd"]
            rt = customer["rt"]
            res.write(f"vrf definition {name}\n")
            res.write(f" rd {rd}\n")
            res.write(f" route-target export {rt}\n")
            res.write(f" route-target import {rt}\n")
            res.write(" address-family ipv4\n")
            res.write(" exit-address-family\n!\n")
        res.write("!\n!\n!\n")

    ## LOOPBACK INTERFACE
    res.write(f"interface Loopback0\n ip address {lpPrefix}{id} 255.255.255.255\n")
    if(igp == "ospf"):
        res.write(f" ip ospf {ospfProcess} area 0\n")
    res.write("!\n")
    
    ## PHYSICAL INTERFACES
    for adj in router["adj"]: # this loops fills egpNeigbors (if the router is an ASBR ofc)
        neighbID = adj["neighbor"]
        neighbAs = [router["as"] for router in routers if router["id"]==neighbID][0]
        preferedAs = As # used for choosing the ip prefixes (either As or neighbAs)
        asInd = asInf[As]["index"]
        neighbAsInd = asInf[neighbAs]["index"]

        for link in adj["links"]:

            ## IP GENERATION
            if link["protocol-type"] == "igp": # routeur a l'interieur de l'AS (pas ASBR)
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
            res.write("interface " + link["interface"] + "\n")
            if link["interface"].startswith("FastEthernet") :
                res.write(" duplex full\n")
            if link["interface"].startswith("GigabitEthernet") :
                res.write(" negotiation auto\n")

            if asType == "provider" and link["protocol-type"] == "egp":
                neighborAs = int(egpNeigbors[-1].split()[1])
                neighbAsName = [client["name"] for client in vrf if neighborAs in client["as"]][0]
                res.write(f" vrf forwarding {neighbAsName}\n")

            res.write(f" ip address {ip} 255.255.255.0\n")

            if link["protocol-type"] == "igp":
                if asType=="provider":
                    res.write(f" mpls ip\n")
                if igp == "ospf":
                    res.write(f" ip ospf {ospfProcess} area 0\n")
                    if "ospf-metric" in link.keys(): # OSPF metric is optional
                        cost = link["ospf-metric"]
                        res.write(f" ip ospf cost {cost}\n")
            
            res.write("!\n")
    res.write("!\n!\n!\n!\n!\n")

    ## EGP
    if egp == "bgp" and isASBR and asType == "provider":
        res.write(f"router bgp {As}\n")
        res.write(f" bgp router-id {id}.{id}.{id}.{id}\n")
        res.write(" bgp log-neighbor-changes\n")

        # iBGP with PE
        for routerID in ASBRlist:
            if routerID != id:
                res.write(f" neighbor {lpPrefix}{routerID} remote-as {As}\n")
                res.write(f" neighbor {lpPrefix}{routerID} update-source Loopback0\n")

        res.write(" address-family vpnv4\n")

        for routerID in ASBRlist:
            if routerID != id:
                res.write(f"  neighbor {lpPrefix}{routerID} activate\n")
                res.write(f"  neighbor {lpPrefix}{routerID} send-community both\n")
        
        res.write(" exit-address-family\n!\n")

        # eBGP with CE
        for customer in vrf:
            custName = customer["name"]
            res.write(f" address-family ipv4 vrf {custName}\n")
            for extNeighb in egpNeigbors:
                ipNeighb = extNeighb.split()[0]
                asNeighb = int(extNeighb.split()[1])
                if asNeighb in customer["as"]:
                    res.write(f"  neighbor {ipNeighb} remote-as {asNeighb}\n")
                    res.write(f"  neighbor {ipNeighb} activate\n")
            res.write(" exit-address-family\n!\n")
            

    if egp == "bgp" and asType == "customer":
        res.write(f"router bgp {As}\n")
        res.write(f" bgp router-id {id}.{id}.{id}.{id}\n")
        res.write(" bgp log-neighbor-changes\n")

        if isASBR :
            for ebgpNeighb in egpNeigbors:
                ipNeighb = ebgpNeighb.split()[0]
                asNeighb = ebgpNeighb.split()[1]
                res.write(f" neighbor {ipNeighb} remote-as {asNeighb}\n")

        for routerID in [router["id"] for router in routers if router["as"]==As]:
            if routerID != id:
                res.write(f" neighbor {lpPrefix}{routerID} remote-as {As}\n")
                res.write(f" neighbor {lpPrefix}{routerID} update-source Loopback0\n")

        res.write(" !\n address-family ipv4\n")

        if isASBR :
            res.write("  redistribute connected\n")
            if(igp == "rip"):
                res.write(f"  redistribute rip {ripName}\n")
            if(igp == "ospf"):
                res.write(f"  redistribute ospf {ospfProcess}\n")
            res.write("  network " + asInf[As]["prefix"] + "0.0\n")
            for ebgpNeighb in egpNeigbors:
                res.write(f"  neighbor {ebgpNeighb.split()[0]} activate\n")
        for routerID in [router["id"] for router in routers if router["as"]==As]:
            if routerID != id:
                res.write(f"  neighbor {lpPrefix}{routerID} activate\n")
        
        res.write(" exit-address-family\n!\n")
    res.write("!\n!\n!\n")

    ## IGP
    if(igp == "ospf"):
        res.write(f"router ospf {ospfProcess}\n router-id {id}.{id}.{id}.{id}\n")
    res.write("!\n!\n!\n")


    '''if isASBR :
        ## ROUTE-MAPS
        res.write(f"route-map CUSTOMERS permit 10\n set local-preference {customPref}\n!\n")
        res.write(f"route-map PEERS permit 10\n set local-preference {peerPref}\n!\n")
        res.write(f"route-map PROVIDERS permit 10\n set local-preference {providerPref}\n!\n")'''


    res.write("control-plane\nline con 0\n exec-timeout 0 0\n privilege level 15\n logging synchronous\n stopbits 1\nline aux 0\n exec-timeout 0 0\n privilege level 15\n logging synchronous\n stopbits 1\nline vty 0 4\n login\n!\nend")
    
    res.close()

    print(f"Router {id} generated")
