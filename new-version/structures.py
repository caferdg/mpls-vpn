class Adj:
    def __init__(self, interface="", neighbor=None, ip=""):
        self.ip = ip
        self.interface = interface
        self.neighbor = neighbor

    def getNeighbIp(self):
        lastBloc = str((int(self.ip[-1])%2) + 1) # switch 1/2
        res = self.ip[:len(self.ip)-1] + lastBloc
        return res

class Router:
    def __init__(self, name="", port=0, id=0, As=None, adjList=None):
        self.name = name
        self.port = port
        self.id = id
        self.As=AS
        self.adjList = adjList

    def isASBR(self):
        for adj in self.adjList:
            if adj.neighbor.As != self.As:
                return True
        return False

class AS:
    def __init__(self, id=0, name="", routerList=None, prefix="", subList=None):
        self.id = id
        self.name = name
        self.routerList = routerList
        self.prefix = prefix
        list = []
        for i in range(0, 255):
            list.append(Subnet(str(i), False))
        self.subList = list
    
    def getASBR(self):
        res = []
        for router in self.routerList:
            if router.isASBR():
                res.append(router)
        return res

    def getSubnet(self):
        for subnet in self.subList:
            if subnet.taken == False:
                subnet.taken = True
                return subnet
        return None

    def freeSubnet(self, subnet):
        for sub in self.subList:
            if sub.num == subnet:
                sub.taken = False
                return
        return 

class Subnet:
    def __init__(self, num="", taken=False):
        self.num = num
        self.taken = False