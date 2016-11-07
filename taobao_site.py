# -*- coding: utf-8 -*-
"""
Created on Sun Oct 16 21:10:42 2016

@author: garfield
"""
# 2016-10-15 重新修改
# 2016-10-17 采集框架更新
# 2016-10-18 更新版程序完成，可以用来采集天猫商店的评论；为了可以加快运行，后续更新版本应该往迭代器方向考虑
# 2016-11-07 后续应该加入评论中图片的获取功能

import requests
import re, os, time, json
import pandas as pd
import random
from pandas.tseries.offsets import Day

class itemList:
    
    def __init__(self, homePage):
        self.homePage = homePage
    
    def getList(self):
#        proxy = {"http":'122.244.20.112:8998'}
        headers = {"user-agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36"}
        urlEnd = "/search.htm?search=y"
        content = requests.get(self.homePage+urlEnd, headers = headers)
        valueEnd = re.findall('id=\"J_ShopAsynSearchURL\" type=\"hidden\" value=\"(.*?)\" />', content.text)
        itemPage = self.homePage+valueEnd[0]
        headers["referer"] = content.url
        newContent = requests.get(itemPage, headers = headers)
        idList = re.findall(r'data-id=\\\"(\d+)\\\">', newContent.text)
        titleList = re.findall(r'<img alt=\\\"(.*?)\\\"', newContent.text)
        itemList = dict(zip(idList, titleList))
        return itemList

class taobaoComment:
    
    def __init__(self, item, itemList, startTime, during = 7):
        self.itemID = item
        self.itemTitle = itemList[item]
        self.startTime = startTime
        self.during = during
        
    def getAppend(self, row):
        appendComment = row["appendComment"]
        if appendComment == "":
            row["appentdDate"] = ""
            row["appendComment"] = ""
            return row
        else:
            row["appentdDate"] = appendComment["days"]
            row["appendComment"] = appendComment["content"]
            return row
        
    def getText(self, page):
        random.seed()
        time.sleep(1)
        times = 0
        url = "https://rate.tmall.com/list_detail_rate.htm"
        params = {"itemID": self.itemID, 
                  "sellerID": "1652864050",
                  "order": "1",
                  "currentPage": page,
                  "append": "0"}
        headers = {"user-agent": "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.75 Safari/537.36",
                   "referer": "https://detail.tmall.com/item.htm?id="+self.itemID+"&scene=taobao_shop"}
        while True:
            try:
                interial = requests.get(url, params = params, headers = headers)
            except ConnectionError:
                print("ConnectionError, try to extend the timeout")
                interial = requests.get(url, params = params, headers = headers, timeout = 60)
            if "rgv587_flag" not in interial.text:
                print("Page %d Finised.." % (page))
                return interial.text
            else:
                time.sleep(abs(random.normalvariate(3, 1)))
                headers["referer"] = interial.url
                times += 1
                print("itemID: " +self.itemID+" Page %d retry %d times" % (page, times))
                if times > 5:
                    raise ConnectionError('Anti-spyder have work 5 times...And I will force stop, please cheak the url: %s'%(interial.url))

    def getPager(self, text):
        paginator = re.findall('\"paginator\":(.*?),\"rateCount\"', text)
        return json.loads(paginator[0])
    
    def strReproduct(self, stringSeries):
        pat1 = '<b></b>'
        pat2 = '&hellip;'
        stringSeries = stringSeries.str.replace(pat1, '')
        stringSeries = stringSeries.str.replace(pat2, '。')
        return stringSeries
    
    def getCite(self, text):
        resultColumns = ["auctionSku", "displayUserNick", "rateDate", "rateContent", "appendComment"]
        jsonFile = re.findall('\"rateList\":(\[.*?\])\,\"searchinfo\"', text)
        tempResult= pd.read_json(jsonFile[0])
#        print(tempResult.columns)
        if tempResult.empty:
            print("Can't read file...")
            return pd.DataFrame()
        result = tempResult[resultColumns]
        result = result.apply(self.getAppend, axis = 1)
        result['auctionSku'] = result['auctionSku'].str.split(':').str[1]
        result['rateDate'] = pd.to_datetime(result['rateDate'], format = "%Y-%m-%d %H:%M:%S")
        result['rateContent'] = self.strReproduct(result['rateContent'])
        result['appendComment'] = self.strReproduct(result['appendComment'])
        result['itemID'] = self.itemID
        startTime = pd.to_datetime(self.startTime, format = "%Y%m%d")
        endTime = startTime - Day(self.during)
        return result[result['rateDate'] > endTime]
    
    def mainProgram(self):
        start = time.time()
        print("itemID: %s( %s ), start." % (self.itemID, self.itemTitle))
        page = 1
        resultComment = pd.DataFrame()
        while True:
            pageText = self.getText(page)
            if page == 1:
                paginator = self.getPager(pageText)
            tempComment = self.getCite(pageText)
            if paginator['items'] == 0:
                print("itemID: " +self.itemID+" is NULL!")
                print("-----")
                return pd.DataFrame()
            resultComment = resultComment.append(tempComment, ignore_index = True)
            if len(tempComment) < 20 or page == paginator['lastPage']:
                end = time.time()
                print("itemID: %s( %s ), Finished in %d s" % (self.itemID, self.itemTitle, (end-start)))
                print("---")
                return resultComment
            else:
                page += 1

def formatOutput(writer):
    workbook = writer.book
    worksheet = writer.sheets['total']
    formatOfTotal = workbook.add_format({'bold': False, 'font_color': 'black', 'align':'center', 'border':1})
    formatOfCite = workbook.add_format({'bold': False, 'font_color': 'black', 'align':'left', 'border':1, 'text_wrap': True})
    worksheet.set_column(0, 0, 9, formatOfTotal)
    worksheet.set_column('B:E', 20, formatOfTotal)
    worksheet.set_column(4, 4, 60, formatOfCite)
    worksheet.set_column(5, 5, 30, formatOfCite)
    worksheet.set_column(6, 6, 12, formatOfTotal)
    worksheet.set_column(7, 7, 12, formatOfTotal)
    
if __name__=='__main__':
    start = time.time()
    print("Start at %s" % start)    
    
    homePage = "https://bananaumbrella.tmall.com"
    itemList = itemList(homePage).getList()
    cwd = os.path.dirname(os.path.realpath(__file__))
    writer = pd.ExcelWriter(cwd+'/cite'+time.strftime('%Y%m%d-%H%M', time.localtime(start))+'.xlsx', engine='xlsxwriter')
    result = pd.DataFrame()
    dayStr = input("Please enter the date,like 20161018: ")    
    during = input("Please enter the day during: ")
    
    for item in itemList:
        newMission = taobaoComment(item, itemList, dayStr, during)
        data = newMission.mainProgram()
        result = result.append(data, ignore_index = True)
        result.to_excel(writer, sheet_name = "total")
    formatOutput(writer)
    writer.save()

    end = time.time()
    time_passed = (end - start)
    print("time used: %d s"% (time_passed))
