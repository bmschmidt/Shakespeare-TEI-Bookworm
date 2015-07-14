#!/usr/bin/python
from xml.dom.minidom import parseString
import re
import json
import sys
import time
import os 
import warnings
import argparse



##########
# Preferences block:
# Some spcial TEI-isms.
##########

"""
In theory, we can search for every single tag.
In practice, this can be extremely inconvenient. For example,
the Folger Shakespeare archive tags each individual word with an xml-id;
while there are sound reasons to this, it mans that we will not be able to capture
any bigrams at all. So any interactions at levels below these tags will be skipped.
The text contained in "w" nodes or "pc" nodes will be harvested, though.
"""

tags_to_ignore = ["w","pc","c","lb"]

#XML:ID is ignored as an attribute, although it *can* be used to build up metadata.
#"Correspondences" are ignored as another type of crosslink to use later.
attributes_to_ignore = ["xml:id","corresp"]



# This is is a bit tricky; specify what fields in the the metadata may be pointed to by other
# fields. This is the sort of thing that could be *learned* as well as *stated*, and
# things would probably be better that way.

"""
The following block is conceptually unnecessary and should be removed.
All text is text--the question is just how we block it off so that most searches will ignore the stuff they don't really want.
"""
nonTextTags = set(["teiHeader","back"])


def derive_additional_fields(derived_fields,dom):
    for key in derived_fields.keys():
        for calling_it in derived_fields[key]:
            new_fields = dict()
            output = open(calling_it + "_json.txt","a")
            dom_elements = dom.getElementsByTagName(key)
            for element in dom_elements:
                attributes = attributes_of_field(element)
                for attribute in attributes.keys():
                    # Don't call it "person_name", call it "sp_who_name" in case, say, there's another case where
                    # it's desirable to get some subset available.
                    try:
                        new_fields[attributes[key]][re.sub("^"+key,calling_it,attribute)] = attributes[attribute]
                    except KeyError:
                        new_fields[attributes[key]] = dict()
                        new_fields[attributes[key]][re.sub("^"+key,calling_it,attribute)] = attributes[attribute]
            for field in new_fields.keys():
                output.write(json.dumps(new_fields[field]) + "\n")    
                
def attributes_of_field(node):
    values = descend(node,[],keep_order=True)
    label = node.getAttribute("xml:id")
    key = node.nodeName
    output = {node.nodeName:label}
    for child in node.childNodes:
        descant = descend(child,[])
        for tagstack in descant.keys():
            thusfar = [node.nodeName]
            # Usually (always?) There will be only one tagstack in a descended doc.
            for pair in tagstack:
                if pair[0].find("_")==-1:
                    #Don't include the composited values.
                    thusfar += [pair[0]]
                if not pair[1] in [True, False, None]:
                    output["_".join([node.nodeName,pair[0]])] = pair[1]
            # If there's a text node at the end, it's an attribute
            # of the master as well
            if descant[tagstack] != "":
                output["_".join(thusfar)] = descant[tagstack]
    output[node.nodeName] = "#" + label
    return output
    

def descend(thisNode,stackOfTags,depth=1,keep_order=False,includeBlank=False):
    """
    A recursive function to go down the XML tree.
    Input: dom element
    Output: a dictionary with tuple-of-tuples keys and text values.
    The tuple keys can be coerced to nested dictionaries giving the metadata
    values for the text.

    They are sorted not in order of appearance but alphabetical order.

    This means a poem inside a play, and a play inside a poem, will have the
    same set of tags unless otherwise defined.
    """

    """
    Step 1: Derive metadata from the node if it's type 1 (an element node).
    This will apply to the text of this element and all its child-elements.
    
    For named nodes, all of the attributes are assigned unless they're explicitly excluded.
    So if there's a line like
        <stage xml:id="stg-1874.0" n="SD 3.1.176.0" type="business" who="#Claudius_Ham #Polonius_Ham">
    the stack will update to include {"stage-type":"business","stage-who":("#Claudius_Ham","#Polonius_Ham),"n"(["SD", "3.1.176.0")}
    """
    if thisNode.nodeType==1:
        """
        For element nodes, we supplement the list of tags with all tags from this
        particular node

        Then proceed (in the next section) to looking at the children with this new set of tags.
        """
        # This is a pui]rocess-wide variable set from the command line.
        global tags_to_ignore
        global attributes_to_ignore
        if thisNode.nodeName in tags_to_ignore:
            pass
        else:
            stackOfTags = stackOfTags + [{thisNode.nodeName:True}]
            for attribute in thisNode.attributes.items():
                # Each attribute is actually a key-value tuple we have to parse.
                if attribute[0] in attributes_to_ignore:
                    continue
                else:
                    values = tuple(attribute[1].split(" "))
                    if len(values)==1:
                        values = values[0]
                    stackOfTags = stackOfTags + [{thisNode.nodeName + "_" + attribute[0]:values}]
    if thisNode.nodeType in [1,9]:
        """
        1 is an element node: 9, also covered, is the main document root here.
        These are nodes that contain other nodes; so what we do is branch down
        each of the chilren and concatenate the results together.
        This is a pretty standard recursion opeation; get the value for each of the
        children, and combine them all together
        """
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
        return thisDocument.summary(keep_order=keep_order)
        # A tuple gives a stable way to represent this dict
        # So that we can match later elements.        

    else:
        """
        There are probably additional types of nodes that need be handled.
        I have not yet encountered them.
        """
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
        except AttributeError:

            raise
    return output
    
class syntheticText(object):
    """
    An individual text built out of a single TEI node.
    It's initialized with a set of tags and a text node:
    it returns a dictionary of the (sorted) tagset pointing
    to the text value of the node.
    """
    def __init__(self,tags,node):
        self.tags = tags
        self.node = node

    def sortTags(self,keep_order):
        tagset = {}
        for element in self.tags:
            for key in element.keys():
                #This should only be one element in the dict ever....
                tagset[key] = element[key]
        if keep_order:
            # Reversing the stack actually keeps the order better,
            # because the most recent one appears first.
            # So that's what we do.
            val = tuple(tagset.iteritems())
            val.reverse()
#            for set in val:
 #               set.reverse()
            return val
        else:
            return tuple(sorted(tagset.iteritems()))

    def summary(self,keep_order=False):
        return {self.sortTags(keep_order=keep_order):self.node.data}

def get_all_text(XMLnode):
    """
    Traverses an XML tree and gets all the text for each node.
    Probably includes a lot of whitespace crud, unless you're careful.

    One of the weird things here is that bigrams may span vast intervening spaces. THis is because you'd *want* them to cross say, a quotation with an intervening footnote; but you
    wouldn't have them to include a single character who doesn't talk for five minute.
    OTOH, you might treat a bigram as spanning the following exchange:
    
    BEN: Are you convinced by what I'm
    YOU: This seems a little a little problematic...
    BEN: saying?
    """
    text = ""
    for a in XMLnode.childNodes:
        if a.nodeType==1:
            text = text + get_all_text(a)
        if a.nodeType==3:
            text = text + a.data
    return text
        
class TEIdocument(object):
    def __init__(self,filename):
        """
        A TEI document is a set of access methods to a TEI file.
        It is initialized with a single filename.
        In cases where headers are stored in separate documents,
        This will need to be expanded.
        """
        self.filename=filename
        self.string = open(filename).read()
        self.dom = parseString(self.string)

    def markup(self):
        """
        This is the master method, that recurses all the way down the tree.
        """
        self.all = descend(self.dom,[])

    def get_all_XML_IDs(self):
        """
        Builds up a list of XML IDs and their attributes so that all those attributes
        can be assigned to any blocks of text that reference them.
        """
        pass
        
    def peopleMetadata(self):
        """
        This should be obviated by the 
        """
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
                        values = {child.nodeName:get_all_text(child)}
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
                docData[fieldname] = get_all_text(tag)
        return docData
                        
    def printOut(self):
        jsonout = open("jsoncatalog.txt","a")
        textout = open("input.txt","a")

        i=1
    
        self.markup()
        docData = self.documentMetadata()
        for key in self.all.keys():
            item = dict(key)
            for fieldName in item.keys():
                if re.search(r"[^A-Za-z0-9_]",fieldName):
                    item[re.sub(r"[^A-Za-z0-9_]","_",fieldName)] = item[fieldName]
                    del (item[fieldName])
            ID = self.filename + "-" + str(i)
            for docKey in docData.keys():
                item[docKey] = docData[docKey]
            item["filename"] = ID
            item["docname"] = self.filename
            item["searchstring"] = "A complicated intersection of tags in " + filename
            jsonout.write(json.dumps(item) + "\n")
            # Replace space plus newline with just one space;
            # but let newlines be whitespace when on their own.
            # I don't believe these characters exist in the TEI.
            correctedString = re.sub(r"[\n\r\t]"," ",self.all[key].encode("utf-8"))
            correctedString = re.sub(r"  +"," ",correctedString)
            textout.write(ID + "\t" + correctedString + "\n")
            i+=1
        jsonout.close()
        textout.close()

def parse_arguments():
    parser = argparse.ArgumentParser(description="Build a bookworm from a (set of) TEI files")
    parser.add_argument("files",nargs="+",help="The TEI files to be parsed")
    config = vars(parser.parse_args())
    return config

if __name__=="__main__":
    config = parse_arguments()
    # Start off by writing to a new file.
    derived_fields = {"person":["sp_who"]}
    derived_files = []
    for key in derived_fields.keys():
        for item in derived_fields[key]:
            derived_files.append(item + "_json.txt")
            
    for filename in ["input.txt","jsoncatalog.txt"] + derived_files:
        try:
            os.remove(filename)
        except OSError:
            print "couldn't find " + filename
            pass
        
    for filename in config["files"]:
        print filename
        docs = TEIdocument(filename)
        docs.printOut()
        
        # There's some useful information about persons in there too.
        derived_fields = {"person":["sp_who"]}
        derive_additional_fields(derived_fields,docs.dom)
        

