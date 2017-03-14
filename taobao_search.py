# -*- coding: utf-8 -*-
"""
Spyder Editor
 
This is a temporary script file.
"""
 
import requests, re, json, sqlite3
from bs4 import BeautifulSoup
import pandas as pd
import datetime
 
class Paser:
    neededColumns = ['category', 'comment_count', 'item_loc', 'nick', 'raw_title', 'view_price', 'view_sales']   
    
    def __init__(self, url):
        self.url = url
       
    def unicodeChange(Str):
        Str = Str.replace('\\u003d','=')
        Str = Str.replace('\\u0026','&')
        return Str
       
    def mainPaser(self):
        Headers = {"User-Agent": "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2049.0 Safari/537.36"}
        Response = requests.get(self.url, headers=Headers)
        Interial = BeautifulSoup(Response.content, 'lxml')
        pageConfig = Interial.find('script', text=re.compile('g_page_config'))
        return pageConfig.string
       
    def dataMaker(self):
        gPageConfig = re.search(r'g_page_config = (.*?);\n', self.mainPaser())
        pageConfigJson = json.loads(gPageConfig.group(1))
        pageItems = pageConfigJson['mods']['itemlist']['data']['auctions']
        pageItemsJson = json.dumps(pageItems)
        pageData = pd.read_json(pageItemsJson)
        neededData = pageData[Paser.neededColumns]
        cityData = neededData['item_loc'].str.split(' ', expand = True)
        cityData.fillna(method = 'pad', axis= 1, inplace= True)
        neededData.loc[:,('item_loc')] = cityData[1]
        neededData.loc[:,('view_sales')] = neededData['view_sales'].str.extract('([\d]*)([\w]*)').get(0)
        neededData.loc[:,('view_sales')] = neededData['view_sales'].astype(int)
        timeNow = datetime.datetime.now()
        neededData['time'] = timeNow.strftime('%Y%m%d%H')
        pd.to_numeric(neededData, errors = 'ignore')
        return neededData.drop(0, axis = 0)
       
    def pagerMaker(self):
        pagerRe = re.search(r'\"pager\":\"(.*?)\",\"tab\"', self.mainPaser())
        pagerStrUni = pagerRe.group(1)
        pagerStr = Paser.unicodeChange(pagerStrUni)
        return 'https:'+ pagerStr + '&s='
       
class Adddata:
    def __init__(self, data):
        self.data = data
        
    def getCenter(city):
        conn = sqlite3.connect('citydata.db')
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS CITYDATA(citycode text primary key , name text, latitude real, longitude real);")
        cursor.execute("SELECT latitude, longitude FROM CITYDATA WHERE name = ?", (city,))
        res = cursor.fetchall()
        if not res:
            payload = {
                'key':'amapkey','keywords':'',
                'subdistrict': '0','showbiz':False,'output':'json',
                }
            payload['keywords'] = city
            jsonData = requests.get('http://restapi.amap.com/v3/config/district?', params = payload)
            jsonText = jsonData.text
            center = re.search(r'\"([\d]*\.[\d]*)\,([\d]*\.[\d]*)\"', jsonText)
            cityCode = re.search(r'\"citycode\"\:\"(\d*)\"', jsonText)
            latitude = float(center.group(2))
            longitude =  float(center.group(1))
            cursor.execute("INSERT INTO CITYDATA VALUES(?, ?, ?, ?);", [cityCode.group(1), city, latitude, longitude])
            cursor.close()
            conn.commit()
            return latitude, longitude
        else:
            res = list(res[0])
            return res[0], res[1]
    
    def updatedData(self):
        df = self.data
        df['latitude'], df['longitude'] = zip(*df['item_loc'].map(Adddata.getCenter))
        return df

class Visualize:
    def __init__(self, data, keyword):
        self.data = data
        self.keyword = keyword
    
    def validated():
        import plotly
        plotly.tools.set_credentials_file(username='yourname', api_key='yourapikey')
    
    def scatterGeo(self):
        import plotly.plotly as py
        
        df = self.data
        length = len(df)
        limits = [(0, int(0.05*length)),(int(0.05*length), int(0.2*length)),(int(0.2*length),int(0.5*length)),(int(0.5*length),length)]
        colors = ["#0A3854","#3779A3", "#1B85C6", "#C0DAEA"]
        cities = []
        
        for i in range(len(limits)):
            lim = limits[i]
            df_sub = newData[lim[0]:lim[1]]
            city = dict(
                type = 'scattergeo',
                locationmode = 'china',
                lon = df_sub['longitude'],
                lat = df_sub['latitude'],
                text = df_sub['nick'],
                marker = dict(
                    size = df_sub['view_sales']/10,
                    color = colors[i],
                    line = dict(width = 0.5, color = '#000'),
                    sizemode = 'area',
                    opacity = 0.5
                ),
                name = "{0} - {1}".format(lim[0], lim[1])
            )
            cities.append(city)
            
        layout = dict(
            title = self.keyword + "的淘宝分布",
            showlegend = True,  
            geo = dict(
                scope = "asia",
                projection = dict(type = 'mercator'),
                showland = True,
                landcolor = 'rgb(217, 217, 217)',
                subunitwidth=1,
                countrywidth=1,
                resolution = 50,
                subunitcolor="rgb(255, 255, 255)",
                countrycolor="rgb(255, 255, 255)",
                lonaxis = dict(range = [newData['longitude'].min()-3, newData['longitude'].max() + 3]),
                lataxis = dict(range = [newData['latitude'].min()-0.5, newData['latitude'].max() + 0.5]),
            ),
        )
        fig = dict(data = cities, layout = layout)
        py.image.save_as(fig, 'd:/my_plot.png', scale = 10)
    
def showPic(pic):
    from IPython.display import Image
    Image(filename = pic)

if __name__ == "__main__":
   
    Url = 'https://s.taobao.com/search?q='
    Keyword = '小黑伞'
    Pages = 1
    
    Pager = Paser(Url+Keyword).pagerMaker()
    dataSet = pd.DataFrame()
    for i in range(Pages):
        newMaker = Paser(Pager + str(i))
        newData = newMaker.dataMaker()
        dataSet = dataSet.append(newData, ignore_index = True)
    newData = Adddata(dataSet).updatedData()
    newGeo = Visualize(newData, Keyword).scatterGeo()
    showPic('d:/my_plot.png')
