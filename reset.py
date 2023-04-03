import sys, os, re

if len(sys.argv) != 2:
    print("Usage: python3 reset.py <projectName>")
    exit(1)

emptyConf = "service timestamps debug datetime msec\nservice timestamps log datetime msec\nno service password-encryption\nip cef\nno ip domain-lookup\nno ip icmp rate-limit unreachable\nip tcp synwait 5\nline con 0\n exec-timeout 0 0\n logging synchronous\n privilege level 15\n no login\nline aux 0\n exec-timeout 0 0\n logging synchronous\n privilege level 15\n no login\nend\n"
projectName = sys.argv[1]
dynamipsPath = os.path.expanduser('~') + "/GNS3/projects/" + projectName + "/project-files/dynamips/"

if not os.path.exists(os.path.expanduser('~') + "/GNS3/projects/" + projectName):
    print("GNS project directory not found!")
    exit(1)

routersDir=[]
for (_, routersName, _) in os.walk(dynamipsPath):
    routersDir.extend(routersName)
    break

routers = {}
# id <-> gnsDir
for routerDir in routersDir:
    for fileName in os.listdir(dynamipsPath + routerDir):
        if fileName.startswith("dynamips_"):
            match = re.search("(?<=_i)(.*?)(?=\_)",fileName)
            id = fileName[match.start():match.end()]
            routers[id] = {}
            routers[id]["gnsPath"] = dynamipsPath + routerDir + "/configs/"

for id in routers:
    res = open(f"{routers[id]['gnsPath']}i{id}_startup-config.cfg", "w")
    res.write(emptyConf)
    res.close()

print(f"{len(routers)} routers cleared!")