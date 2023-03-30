import json

def manageVRF(newList, oldJSON):
    oldList = oldJSON["vrfs"]
    sharedVrf = []
    addedVRF = []
    for newVrf in newList:
        found = False
        for oldVrf in oldList:
            if newVrf["name"] == oldVrf["name"]:
                sharedVrf.append(newVrf)
                found = True
                break
        if not found:
            addedVRF.append(newVrf)
    removedVRF = [vrf for vrf in oldList if vrf (not in sharedVrf) and (vrf not in addedVRF)]
    return (sharedVrf, addedVRF, removedVRF)