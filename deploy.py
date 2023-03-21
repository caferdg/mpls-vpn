import os, sys, re, shutil

if len(sys.argv) != 3:
    print("Usage: python3 deploy.py <confFilePath> <projectName>")
    exit(1)

confDir = sys.argv[1]
if confDir.endswith("/"):
    confDir = confDir[:-1]
projectName = sys.argv[2]
dynamipsPath = os.path.expanduser('~') + "/GNS3/projects/" + projectName + "/project-files/dynamips/"

if not os.path.exists(os.path.expanduser('~') + "/GNS3/projects/" + projectName):
    print("GNS project directory not found!")
    exit(1)

if len(os.listdir(confDir))==0:
    print("Configurations' directory empty, you must first generate these files.")
    exit(1)

routersDir=[]
for (_, routersName, _) in os.walk(dynamipsPath):
    routersDir.extend(routersName)
    break

routers = {}

# id <-> gnsDir
for routerDir in routersDir:
    for fileName in os.listdir(dynamipsPath + routerDir + "/configs/"):
        if fileName.endswith("_startup-config.cfg"):
            match = re.search("(?<=i)(.*?)(?=\_)",fileName)
            id = fileName[match.start():match.end()]
            routers[id] = {}
            routers[id]["gnsPath"] = dynamipsPath + routerDir + "/configs/"

for id in routers:
    # if startup-config already exists in gns dir
    if os.path.isfile(f"{routers[id]['gnsPath']}i{id}_startup-config.cfg"):
        os.remove(f"{routers[id]['gnsPath']}i{id}_startup-config.cfg")
    
    shutil.move(f"{confDir}/i{id}_startup-config.cfg", routers[id]["gnsPath"])

print(f"{len(routers)} files moved from {confDir} to GNS directories!")
