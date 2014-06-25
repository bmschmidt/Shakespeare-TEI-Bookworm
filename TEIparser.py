#!/usr/bin/python
import roman
from xml.dom.minidom import parseString
import re
import json
import sys
import time
import os 
import warnings


##########
# Preferences block:
# Some spcial TEI-isms.
##########

wordLevelTags = ["w","pc","c","lb"]

# These are tags or tag combinations that will be ignored
# So, for example, "w-n" means that all n attributes of
# tags named "w" will be ignored.
# XML:id is among the things skipped.
skipList = set(["xml:id","c-n","w-n","pc-n","corresp"])
nonTextTags = set(["teiHeader","back"])





import random

def descend(thisNode,stackOfTags,depth=1):
    """
    A recursive function to go down the XML tree.
    Input: dom element
    Output: a dictionary with tuple-of-tuples keys and text values.
    The tuple keys can be coerced to dictionaries giving the metadata
    values for the text.
    """



    
    """
    Step 1: Derive metadata from the node if it's type 1 (an element node).
    This will apply to the text of this element and all its child-elements.
    
    For named nodes, all of the attributes are assigned unless they're explicitly excluded.
    So if there's a line like
        <stage xml:id="stg-1874.0" n="SD 3.1.176.0" type="business" who="#Claudius_Ham #Polonius_Ham">
    the stack will update to include {"stage-type":"business","stage-who":("#Claudius_Ham","#Polonius_Ham),"n"(["SD", "3.1.176.0")}
    but since we drop "xml:id", that won't be assigned.
    """
    if thisNode.nodeType==1:
        for attribute in thisNode.attributes.items():
            if attribute[0] not in skipList:
                if thisNode.nodeName + "_" + attribute[0] not in skipList:
                    values = tuple(attribute[1].split(" "))
                    if len(values)==1:
                        values = values[0]
                    stackOfTags = stackOfTags + [{thisNode.nodeName + "_" + attribute[0]:values}]
        if len(thisNode.attributes.items()) == 0:
            # If it's a tag with no values, we still need to know:
            # Setting it to the text string "true" rather than the logical value
            # for bad reasons.
            stackOfTags = stackOfTags + [{thisNode.nodeName:"true"}]
            
    if thisNode.nodeType in [1,9]:
        # 1 is an element node: 9, also covered, is the main document root here.
        children = thisNode.childNodes
        document = {}
        if thisNode.nodeName not in nonTextTags:
            for child in children:
                childValue = descend(child,stackOfTags,depth+1)
                document = combineTwoTexts(document,childValue)
        return document

    if thisNode.nodeType==3:
        #3 is a text node: that's when we really dump out some text.
        thisDocument = syntheticText(stackOfTags,thisNode)
        return thisDocument.summary()
        # A tuple gives a stable way to represent this dict
        # So that we can match later elements.        

    else:
        print "Skipping over node because it's of some unfamiliar type:"
        print thisNode.nodeType
        return {}

def combineTwoTexts(output,supplement):
    """
    Here a text is a tuple key with the text associated with it:
    As long as two texts have the same tuple key, we just combine them together.
    """
    for key in supplement.keys():
        try:
            output[key] = output[key] + " " + supplement[key]
        except KeyError:
            output[key] = supplement[key]
    return output
    
class syntheticText(object):
    """
    An individual text built out of a single TEI node.
    It's initialized with a set of tags and a text noe:
    it returns a dictionary of the (sorted) tagset pointing
    to the text node.
    """
    def __init__(self,tags,node):
        self.tags = tags
        self.node = node

    def sortTags(self):
        tagset = {}
        for element in self.tags:
            for key in element.keys():
                #This should only be one deep ever....
                tagset[key] = element[key]
        return tuple(sorted(tagset.iteritems()))
    
    def summary(self):
        return {self.sortTags():self.node.data}

def getAllText(XMLnode):
    """
    Traverses an XML tree and gets all the text for each node.
    Probably includes a lot of whitespace crud, unless you're careful.
    """
    text = ""
    for a in XMLnode.childNodes:
        if a.nodeType==1:
            text = text + getAllText(a)
        if a.nodeType==3:
            text = text + a.data
    return text
        
class TEIdocument(object):
    def __init__(self,filename):
        self.filename=filename
        self.string = open(filename).read()
        self.dom = parseString(self.string)

    def markup(self):
        self.all = descend(self.dom,[])

    def peopleMetadata(self):
        #This is UUUUUGLY deep.
        peopleData = dict()
        group = "listPerson"
        element = "person"
        reftag = "who"
        for group in self.dom.getElementsByTagName("listPerson"):
            for person in group.getElementsByTagName("person"):
                XMLid = person.getAttribute("xml:id")
                entry = {reftag:"#"+XMLid}
                for child in person.childNodes:
                    if child.nodeType==1:
                        values = {child.nodeName:getAllText(child)}
                        otherValues = dict(child.attributes.items())
                        for key in otherValues.keys():
                            values[childNode.nodeName + "_" + key] = otherValues[key]
                        for key in values.keys():
                            entry[key] = values[key]
                print json.dumps(entry)

    def documentMetadata(self):
        fileDesc = self.dom.getElementsByTagName("fileDesc")[0]
        docData = {}
        for fieldname in ["title","author","editor"]:
            for tag in fileDesc.getElementsByTagName(fieldname):
                docData[fieldname] = getAllText(tag)
        return docData
                        
    def printOut(self,wtype="w"):
        jsonout = open("jsoncatalog.txt",wtype)
        textout = open("input.txt",wtype)

        i=1
    
        self.markup()
        docData = self.documentMetadata()
        for key in self.all.keys():
            item = dict(key)
            for fieldName in item.keys():
                if re.search(r"[^A-Za-z0-9_]",fieldName):
                    item[re.sub(r"[^A-Za-z0-9_]","_",fieldName)] = item[fieldName]
                    del (item[fieldName])
            
            ID = self.filename+"-" + str(i)
            for docKey in docData.keys():
                item[docKey] = docData[docKey]
            item["filename"] = ID
            item["docname"] = self.filename
            item["searchstring"] = "A complicated intersection of tags in " + filename
            jsonout.write(json.dumps(item) + "\n")
            textout.write(ID + "\t" + re.sub("[\n\r\t]"," ",self.all[key].encode("utf-8")) + "\n")
            i+=1

if __name__=="__main__":
    path = "TEIfiles/Folger_Digital_Texts_Complete"
    mode = "w"
    for filename in os.listdir(path):
        if filename.endswith("xml"):
            print filename
            docs = TEIdocument(path + "/" + filename)
            docs.printOut(mode)
            mode = "a" #hacky way to make it switch to appending after the first document.
