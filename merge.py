#!/usr/bin/python

from zipfile import ZipFile
from xml.dom.minidom import parseString
from zlib import decompress
import Image
from os import system,sep
from sys import argv
from reportlab.pdfgen import canvas
from io import BytesIO
from reportlab.pdfbase.pdfutils import ImageReader
from re import sub
from tempfile import gettempdir
import webbrowser
from xml.dom import minidom, getDOMImplementation

def showUsage():
	print """
	Usage: snbopen snbfile [pdffile]
		snbopen opens .snb files created by samsung tablets
		if pdf file is specified the program converts the snb file to the pdf.
	"""

def zipRead(zipFile,filename):
	tempFile = zipFile.open(filename)
	raw = tempFile.read()
	tempFile.close()
	return raw

def addImage(snbFile,canvas,image,rels,element):
	imgFileName = "snote/"+rels[image.getAttribute("r:id")]
	imgStr = zipRead(snbFile,imgFileName)
	if imgFileName.endswith(".zdib"):
		imgStr = decompress(imgStr)
		width = ord(imgStr[5]) * 256 + ord(imgStr[4])
		height = ord(imgStr[9]) * 256 + ord(imgStr[8])
		img = Image.fromstring("RGBA",(width,height),imgStr[52:])
		canvas.drawInlineImage(alpha_to_color(img),0,0,595.27,841.89)
	else:
		style = imagePoss(element.getElementsByTagName("v:shape")[0].getAttribute("style"))
		img=Image.open(BytesIO(imgStr))
		canvas.drawInlineImage(img,style.left,style.bottom,style.width,style.height)


def addText(canvas,element,styles):
	for run in element.getElementsByTagName("sn:r"):
		if(len(run.getElementsByTagName("sn:t")) > 0):
			##TODO: support italic, bold and underlined text
			charStyle = styles["Character" + run.getAttributeNode("sn:rStyle").value]
			text=run.getElementsByTagName("sn:t")[0].firstChild.nodeValue
			canvas.setFont("Helvetica",charStyle.size)
			canvas.setFillColor(charStyle.color)
			canvas.drawString(40,810-charStyle.size,text)
			##TODO: support non-unicode characters


def readRelsFile(snbFile):
	relations = parseString(zipRead(snbFile,"snote/_rels/snote.xml.rels"))
	rels=dict()
	for relation in relations.getElementsByTagName("Relationship"):
		rels[relation.getAttribute("Id")] = relation.getAttribute("Target")
	return rels

def mergeRelsFile(snbFile_a, snbFile_b):
	
	relations_a = parseString(zipRead(snbFile_a,"snote/_rels/snote.xml.rels"))
	relations_b = parseString(zipRead(snbFile_b,"snote/_rels/snote.xml.rels"))
	
	rels=dict()
	rIds=[]
	for relation in relations_a.getElementsByTagName("Relationship"):
		rId = relation.getAttribute("Id")
		rIds.append(int(rId[3:]))
		rels[rId] = relation.getAttribute("Target")
	
	offset = max(rIds)
	relationships = relations_a.getElementsByTagName("Relationships")[0]

	for relation in relations_b.getElementsByTagName("Relationship"):
		rId = relation.getAttribute("Id")
		rId = 'rId' + str(int(rId[3:]) + offset)
		rels[rId] = relation.getAttribute("Target")
		relation.setAttribute("Id", rId)
		relationships.appendChild(relation)
		
	print relations_a.toxml()
	return (rels, offset, relations_a)


def readCharStyles(snbFile):
	styles = parseString(zipRead(snbFile,"snote/styles.xml"))
	charStyles = dict()
	for style in styles.getElementsByTagName("sn:style"):
		if style.getAttributeNode("sn:type").value == "character":
			if len(style.getElementsByTagName("sn:color"))>0:
				color = style.getElementsByTagName("sn:color")[0].getAttribute("sn:val")
			else:
				color = "000000"
			if len(style.getElementsByTagName("sn:sz"))>0:
				size = int(style.getElementsByTagName("sn:sz")[0].getAttribute("sn:val"))*.5
			else:
				size = 16
			charStyles[style.getAttribute("sn:styleId")] = Style(len(style.getElementsByTagName("sn:b"))>0,
				len(style.getElementsByTagName("sn:i"))>0, len(style.getElementsByTagName("sn:u"))>0,color,size)
	return charStyles


class Style:
	def __init__(self, bold, italic, underline,color="000000",size=48):
		self.bold = bold
		self.italic = italic
		self.underline = underline
		self.color = "0X"+color
		self.size=size


class imagePoss:
	def __init__(self,style):
		info = sub(r'[A-Za-z\-:]',"",style).split(";")
		self.left=float(info[2])
		self.bottom=841.89 -(float(info[3])+float(info[5]))
		self.width = float(info[4])
		self.height = float(info[5])


def alpha_to_color(image, color=(255, 255, 255)):
    image.load()  # needed for split()
    background = Image.new('RGB', image.size, color)
    background.paste(image, mask=image.split()[3])  # 3 is the alpha channel
    return background

def printSnb(snbname_a):
	
	snbFile_a = ZipFile(snbname_a,"r")
	
	snote_a = parseString(zipRead(snbFile_a,"snote/snote.xml"))
	
	bodyElements_a = snote_a.firstChild.firstChild.childNodes
	
	print '\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n'

	for element in bodyElements_a:	
		if element.nodeName == "sn:SNoteObj":
			print element.toxml()
		
	print '\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n'

	for t in ((name, snbFile_a.open(name)) for name in snbFile_a.namelist()):
		print t[0]
	

	snbFile_a.close()
	


def mergeSnbs(snbname_a, snbname_b, rename):
	
	#
	snbFile_a = ZipFile(snbname_a,"r")
	snbFile_b = ZipFile(snbname_b,"r")
	snbFile_c = ZipFile(rename,"w")

	#
	rels, offset, relations = mergeRelsFile(snbFile_a, snbFile_b)

	#
	snote_a = parseString(zipRead(snbFile_a,"snote/snote.xml"))
	snote_b = parseString(zipRead(snbFile_b,"snote/snote.xml"))

	bodyElements_a = snote_a.firstChild.firstChild.childNodes
	bodyElements_b = snote_b.firstChild.firstChild.childNodes

	for element in bodyElements_b:	
		if element.nodeName == "sn:SNoteObj":
			images=element.getElementsByTagName("v:imagedata")
			for image in images:
				rId = image.getAttribute("r:id")
				rId = "rId" + str(int(rId[3:]) + offset)
				image.setAttribute("r:id", rId)
			bodyElements_a.append(element)
		else:
			bodyElements_a.append(element)

	start = True
	for t in ((name, snbFile_a.open(name)) for name in snbFile_a.namelist()):
		if t[0] == 'snote/snote.xml':
			snbFile_c.writestr(t[0], snote_a.toxml())
		elif t[0] == "snote/_rels/snote.xml.rels":
			snbFile_c.writestr(t[0], relations.toxml())
		else :			
			if 'snote/media/snb_thumbnailimage' in t[0] and start:
				for a in ((name, snbFile_b.open(name)) for name in snbFile_b.namelist()):
					if 'snote/media/fImage' in a[0]:
						snbFile_c.writestr(a[0], a[1].read())			
				start = False
			
			snbFile_c.writestr(t[0], t[1].read())

	snbFile_a.close()
	snbFile_b.close()
	snbFile_c.close()

if len (argv)==4:
	mergeSnbs(argv[1],argv[2],argv[3])
	printSnb(argv[3])
else:
	showUsage()