import os, sys, time, re

def mergeLog():
    xmlHeader = '<?xml version="1.0" encoding="UTF-8"?>'
    daisyHeader = '<daisy time="' + time.strftime('%Y/%m/%d %X') + '">'
    daisyEnder = '</daisy>'

    xmlList = []
    xmlList.append(xmlHeader)
    xmlList.append(daisyHeader)

    for root, _, files in os.walk(r'.'):
        for filename in files:
            if (os.path.splitext(filename)[0] != 'daisy'
                and os.path.splitext(filename)[0] != 'daisy_sonar'
                and os.path.splitext(filename)[1] == '.xml') :
                filepath = os.path.join(root, filename)
                fin = open(filepath)
                xmlList.append(fin.read()[len(xmlHeader):])
                fin.close()

    xmlList.append(daisyEnder)
    text = ''.join(xmlList)

    text = re.sub('message=".*?"', 'message=""', text)
    fout = open('./daisy.xml', 'w')
    fout.write(text)
    fout.close()

    text = re.sub('<!\[CDATA\[.*?\]\]>', '', text, flags=re.S)
    fout = open('./daisy_sonar.xml', 'w')
    fout.write(text)
    fout.close()

mergeLog()