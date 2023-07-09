import os
import datetime


# ==================================================================================
# General Number Functions
# ==================================================================================
def to_num(s):
    try:
        return int(s)
    except ValueError:
        return float(s)

def sig_round(f,n=3):
    if int(f) == f:
        return(f)
    else:
        return(float(f"{f:.{n}g}"))


# ==================================================================================
# General utilities for processing List, Dictionaries
# ==================================================================================

#-----------------------------------------------------------------------------------
def split_StrList(strList,sep=";"):
#-----------------------------------------------------------------------------------
    if strList:
        retLst = str(strList).split(sep)
        for i in range(len(retLst)):
            retLst[i] = retLst[i].strip()
    else:
        retLst = None
    return(retLst)

#-----------------------------------------------------------------------------
def limit_StrList(strLst,maxLenght=1024,sep="; "):
    if sep in strLst:
        while len(strLst) > maxLenght:
            strLst = strLst[:strLst.rfind(sep)]
    else:
        strLst = strLst[:(maxLenght-1)]
    return(strLst)

#-----------------------------------------------------------------------------
# Split/Merge Function
#-----------------------------------------------------------------------------
def strList_to_List(cStr,sep=';',size=0,fill=None):
    if sep in cStr:
        splitLst = list(cStr.split(sep))
        stripLst = list(map(str.strip, splitLst))
        return(resize_lst(stripLst,size,fill))
    else:
        return(resize_lst([cStr],size,fill))


#-----------------------------------------------------------------------------
def limit_lst(lst,maxLst=10,lastItem=None):
    """
    Limit list to maxLst entries 
    """
    if maxLst:
        if len(lst) > maxLst:
            x = lst[:maxLst]
            if lastItem:
                x.append(lastItem)
            return(x)
    return(lst)

#-----------------------------------------------------------------------------
def resize_lst(lst,size,fill=None):
    """
    Fill List to size entries using fill as filler
    """
    if size>0:
        if len(lst)>size:
            lst = lst[:size]
        else:
            lst += [fill]*(size-len(lst))
    return(lst)

#-----------------------------------------------------------------------------
def clean_list(lst):
    """
    Remove None entries from List
    """
    lst = [x for x in lst if x is not None]
    return(lst)

#-----------------------------------------------------------------------------
def join_lst(cList,sep=';'):
    """
    Join list into StrList 
    """
    if isinstance(cList,list):
        sList = [str(x) for x in cList if x is not None]
        if len(sList)==0:
            return(None)
        elif len(sList)>1:
            return(sep.join(sList))
        else:
            return(sList[0])        
    else:
        return(str(cList))


# ==================================================================================
# General utilities for processing Files and Folders
# ==================================================================================

#-----------------------------------------------------------------------------
def listFolders(Path):
    return([ name for name in os.listdir(Path) if os.path.isdir(os.path.join(Path, name)) ])
#-----------------------------------------------------------------------------
def listFiles(Path):
    return([ name for name in os.listdir(Path) if os.path.isfile(os.path.join(Path, name)) ])
#-----------------------------------------------------------------------------

#-----------------------------------------------------------------------------
# Estimated time : t = Timer(12987) ... print(t.remains(37))
#-----------------------------------------------------------------------------
class Timer(object):
    def __init__(self, total):
        self.start = datetime.datetime.now()
        self.total = total
 
    def remains(self, done):
        now  = datetime.datetime.now()
        #print(now-start)  # elapsed time
        time_spent = (now - self.start)
        time_left = (self.total - done) * (time_spent) / done
    
        sec_left = int(time_left.total_seconds())
        hms_left = datetime.timedelta(seconds=sec_left)
        sec_spent = int(time_spent.total_seconds())
        hms_spent = datetime.timedelta(seconds=sec_spent)

        return(str(hms_left),str(hms_spent))

    def format_sec_to_hms(seconds):
        hours = seconds // (60*60)
        seconds %= (60*60)
        minutes = seconds // 60
        seconds %= 60
        return "%02i:%02i:%02i" % (hours, minutes, seconds)
