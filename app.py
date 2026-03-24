from flask import Flask, request, jsonify, render_template_string
import requests, threading, webbrowser, math

app = Flask(__name__)

# ====== FREE CESIUM TOKEN ======
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiI4M2YwYTc0Zi05Y2FlLTRjZWEtYWQxNS1mOThkNmQ4YjY5NGUiLCJpZCI6MzkyNzQ0LCJpYXQiOjE3NzE2ODM4ODl9.THiY49d8xsrS9WA_qr6IOAiptgfZ12sgVlAI-NmHlII"
# =================================


def safe(url, name="API"):

    try:

        r = requests.get(url, timeout=6,
        headers={"User-Agent":"Mozilla/5.0"})

        if r.status_code != 200:

            print(f"❌ {name} FAILED | STATUS:", r.status_code)

            return None

        print(f"✅ {name} OK")

        return r.json()

    except Exception as e:

        print(f"❌ {name} ERROR:", e)

        return None

def place_name(lat, lon):
    d = safe(f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json", "place")
    if d and "display_name" in d:
        return d["display_name"]
    return "Unknown Sector"


def elevation(lat, lon):
    d = safe(f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}","elevation")
    if d and "elevation" in d:
        return d["elevation"][0]
    return 0


def rain_24h(lat, lon):
    d = safe(
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation&past_days=1",
        "rain"
    )
    if d and "hourly" in d:
        return sum(d["hourly"]["precipitation"])
    return 0


def earthquakes(lat, lon):
    d = safe(
        f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&latitude={lat}&longitude={lon}&maxradiuskm=200",
        "earthquakes"
    )
    if d and "features" in d:
        return len(d["features"])
    return 0


def slope_angle(lat, lon):
    delta = 0.01
    east = elevation(lat, lon + delta)
    west = elevation(lat, lon - delta)
    north = elevation(lat + delta, lon)
    south = elevation(lat - delta, lon)

    dz_dx = (east - west) / 2000
    dz_dy = (north - south) / 2000

    slope = math.degrees(math.atan(math.sqrt(dz_dx**2 + dz_dy**2)))
    return abs(slope)

def flood_risk(elev, rain):
    if elev<100 and rain>40:
        return"HIGH FLOOD RISK"
    elif elev<200 and rain>20:
        return"MADERATE FLOOD RISK"
    else:
        return"LOW FLOOD RISK"

def rain_level(rain):
    if rain<10:
        return"LIGHT RAIN"
    elif rain<40:
        return"MADERATE FLOOD RISK"
    else:
        return"HEAVY RAIN"
    
def terrain_type(slope):

    if slope < 5:
        return "FLAT LAND"

    elif slope < 20:
        return "HILLY TERRAIN"

    else:
        return "MOUNTAIN REGION"
    
# def soil_moisture(lat, lon):

#     rain = rain_24h(lat, lon)

#     # simple soil wetness model

#     if rain < 2:
#         return 0.1

#     elif rain < 10:
#         return 0.3

#     elif rain < 30:
#         return 0.6

#     else:
#         return 0.9 

def rain_intensity(lat, lon):

    d = safe(
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation",
        "hourly_rain"
    )

    try:
        # last 6 hours rain
        rain = sum(d["hourly"]["precipitation"][:6])
        return rain

    except:
        return 0
    
def soil_moisture(lat, lon):

    url = f"https://power.larc.nasa.gov/api/temporal/daily/point?latitude={lat}&longitude={lon}&parameters=PRECTOT,RH2M&start=20240101&end=20240101&community=AG&format=JSON"

    d = safe(url, "NASA")

    try:
        rain = list(d["properties"]["parameter"]["PRECTOT"].values())[0]
        humidity = list(d["properties"]["parameter"]["RH2M"].values())[0]

        soil = (rain * 0.04) + (humidity * 0.01)

        print("🌍 NASA Soil:", soil)

        return round(min(1, soil), 2)

    except Exception as e:
        print("❌ NASA ERROR:", e)

        # 🔁 fallback (VERY IMPORTANT)
        rain = rain_24h(lat, lon)
        slope = slope_angle(lat, lon)

        soil = (rain * 0.04)  -(slope * 0.01)
        soil =max(0,soil)

        print("⚡ Fallback Soil:", soil)

        return round(max(0,min(1, soil)), 2)
    
def ndvi_index(lat, lon):

    rain = rain_24h(lat, lon)
    
    d = safe(
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=relative_humidity_2m",
        "humidity"
    )

    try:
        humidity = d["hourly"]["relative_humidity_2m"][0]
    except:
        humidity = 50

    slope = slope_angle(lat, lon)

    # NDVI estimation
    ndvi = (humidity * 0.004) + (rain * 0.002) - (slope * 0.003)

    return round(max(0, min(1, ndvi)), 2)

def future_landslide(lat, lon):

    d = safe(
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation&forecast_days=2",
        "future_rain"
    )

    result = []

    try:
        for i in range(0, 12):   # next 12 hours

            rain = d["hourly"]["precipitation"][i]

            prob = min(100, int(rain * 5))

            result.append({
                "hour": i,
                "rain": rain,
                "risk": prob
            })

    except:
        pass

    return result

def weather_forecast(lat, lon):

    d = safe(
    f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,precipitation_probability&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&forecast_days=7",
    "weather"
    )

    if not d:
        return {}

    hourly = []
    for i in range(0,24,3):
        hourly.append({
            "time": d["hourly"]["time"][i],
            "temp": d["hourly"]["temperature_2m"][i],
            "rain": d["hourly"]["precipitation_probability"][i]
        })

    daily = []
    for i in range(7):
        daily.append({
            "day": d["daily"]["time"][i],
            "tmax": d["daily"]["temperature_2m_max"][i],
            "tmin": d["daily"]["temperature_2m_min"][i],
            "rain": d["daily"]["precipitation_probability_max"][i]
        })

    return {"hourly":hourly,"daily":daily}

def calculate_risk(lat, lon):

    elev = elevation(lat, lon) or 0
    rain = rain_24h(lat, lon) or 0
    quakes = earthquakes(lat, lon) or 0
    slope = slope_angle(lat, lon) or 0
    soil = soil_moisture(lat, lon) or 0
    ndvi= ndvi_index(lat,lon)
    future= future_landslide(lat, lon)
    flood = flood_risk(elev, rain)
    terrain = terrain_type(slope)
    rain_type = rain_level(rain)


    # NORMALIZATION
    rain_n = min(rain / 50, 1)        # 0–50 mm scale
    slope_n = min(slope / 45, 1)      # 0–45° scale
    soil_n = min(soil, 1)             # already 0–1
    rain_h = rain_intensity(lat, lon)   
    rain_h_n = min(rain_h / 20, 1)      
    quake_n = min(quakes / 10, 1)     # max 10 quakes

# WEIGHTED SCORE (balanced)

    score = (
    slope_n * 0.30 +
    rain_n  * 0.25 +
    soil_n  * 0.20 +
     rain_h_n * 0.15 +
    (1-ndvi) * 0.10
)
    score = max(0,min(score,1))
    probability = round(score * 100)

   
    # flat land protection
    if slope < 5:
        probability = int(probability*0.3)

    if probability < 30:
        risk = "LOW"
        color = "#15b946"
    elif probability < 60:
        risk = "MODERATE"
        color = "#ffd000"
    elif probability < 80:
        risk = "HIGH"
        color = "#da5c14"
    else:
        risk = "EXTREME"
        color = "#ff0055"

    return {
        "place": place_name(lat, lon),
        "risk": risk,
        "prob": probability,
        "color": color,
        "elev": round(elev,1),
        "rain": round(rain,1),
        "soil": round(soil,2),
        "quakes": quakes,
        "slope": round(slope,1),
        "terrain": terrain,
        "rain_type": rain_type,
        "ndvi": ndvi,
        "future":future,
        "rain_hour" : round(rain_h,1), 
         "flood": flood
    }


html = """
<!DOCTYPE html>
<html>
<head>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script src="https://cesium.com/downloads/cesiumjs/releases/1.111/Build/Cesium/Cesium.js"></script>
<link href="https://cesium.com/downloads/cesiumjs/releases/1.111/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
<meta name="viewport" content="width=device-width, initial-scale=1.0,maximum-scale=1.0,user-scalable=no">

<style>
html,body {
    margin: 0;
    padding-top: env(safe-area-inset-top);
    padding-bottom: env(safe-area-inset-bottom);
background:#050510;color:#00ffff;font-family:Orbitron,Segoe UI
overflow:hidden;
}
#map{width:100%;height:100%}

/* SCI FI BRAND */
#brand{
position:absolute;   /* 👈 sabse important */
left:20px;           /* 👈 left corner */
top:calc(20px + env(safe-area-inset-top));

background:rgba(0,0,30,0.7);
border:1px solid #00ffff;
border-radius:30px;
box-shadow:0 0 20px #00ffff;
letter-spacing:2px;
padding:10px 18px;
z-index:9999;
}

/* HUD COORDS */
#coordsBar{
position:absolute;
left:50%
 top:calc(20px + env(safe-area-inset-top));
transform:translateX(-50%);
background:rgba(0,0,0,0.6);
padding:6px 15px;
border:1px solid #00ffff;
border-radius:20px;
box-shadow:0 0 10px #00ffff;
z-index:9999;
}

/* CLEAR BTN */
#clearBtn{
position:absolute;
bottom:30px;
right:20px;
padding:10px 18px;
background:#000;
color:#00ffff;
border:1px solid #00ffff;
border-radius:30px;
box-shadow:0 0 15px #00ffff;
cursor:pointer;
display:none;
z-index:10;
}

/* RADAR LOADER */
#loader{
position:absolute;
top:50%;
left:50%;
transform:translate(-50%,-50%);
width:30px;
height:30px;
border-radius:50%;
border:3px solid #00ffff;
border-top:3px solid transparent;
animation:spin 1s linear infinite;
display:none;
z-index:20;
}
#insta {
font-size:12px;
margin-top:4px;
text-align:center;
}

#insta a {
color:#ff00ff;
text-decoration:none;
transition:0.3s;
}

#insta a:hover {
color:#ffffff;
text-shadow:0 0 8px #ff00ff;
}

.spinLoader{
position:absolute;
width:26px;
height:26px;

border:3px solid #00ffff;
border-top:3px solid transparent;

border-radius:50%;

animation:spin 1s linear infinite;

}
@keyframes spin{
0%{transform:translate(-50%,-50%) rotate(0deg)}
100%{transform:translate(-50%,-50%) rotate(360deg)}
}
#locBtn{
position:absolute;
bottom:90px;
right:20px;
background:black;
border:1px solid #00ffff;
border-radius:50%;
padding:12px;
cursor:pointer;
box-shadow:0 0 12px #00ffff;
z-index:9999;
font-size:18px;
}
#moreBtn{
position:absolute;
top:80px;
right:20px;
background:black;
border:1px solid #00ffff;
padding:10px;
cursor:pointer;
z-index:9999;
border-radius:8px;
box-shadow:0 0 10px #00ffff;
}

# #sidePanel{
# position:absolute;
# top:0;
# right:-320px;
# width:300px;
# height:100%;
# background:rgba(0,0,0,0.95);
# border-left:1px solid #00ffff;
# padding:15px;
# transition:0.3s;
# z-index:9998;
# overflow-y:auto;
# }

# #sidePanel.active{
# right:0;
# }
# #sidePanel.active{
# right:0;
# }
#app {
    width: 1920px;
    height: 1080px;
    transform-origin: top left;
    position: relative;
}
# canvas{
# width:100% !important;
# height:180px !important;
# }
</style>
</head>
<body>
<div id= "app">

<div id="brand">
    ⚡ PRAVEEN GEO LAB ⚡
    <div id="insta">
        <a href="https://instagram.com/___thakur_77___" target="_blank">
              📸@___thakur_77___
        </a>
    </div>
</div>
<div id="coordsBar">SCANNING...</div>
<div id="loader"></div>
<div id="clearBtn">RESET SCAN</div>
<div id="locBtn">📍</div>
<div id="map"></div>


<script>
if (navigator.hardwareConcurrency <= 4 || navigator.deviceMemory <= 2) {
    window.location.href = "/lite";
}

Cesium.Ion.defaultAccessToken="%TOKEN%";

var viewer=new Cesium.Viewer("map",{

terrainProvider:new Cesium.EllipsoidTerrainProvider(),

animation:false,

maximumRenderTimeChange:Infinity,

requestRenderMode:true,

shadows:false,

timeline:false,

baseLayerPicker:true,

geocoder:false,

sceneModePicker:true,

navigationHelpButton:false,
homeButton:true

});

viewer.scene.globe.enableLighting=false;

var markers=[];
var rainChart = null;
var rainChart = null;

var markerMap={}

// USER LOCATION BUTTON

document.getElementById("locBtn").onclick=function(){

navigator.geolocation.getCurrentPosition(function(pos){

let lat=pos.coords.latitude
let lon=pos.coords.longitude

viewer.camera.flyTo({
destination:Cesium.Cartesian3.fromDegrees(lon,lat,400)
})

viewer.entities.add({
position:Cesium.Cartesian3.fromDegrees(lon,lat,),
point:{
pixelSize:14,
color:Cesium.Color.CYAN,
outlineColor:Cesium.Color.WHITE,
outlineWidth:2
}
})

})

}

// HUD COORDS
viewer.screenSpaceEventHandler.setInputAction(function(click){

var rect = viewer.canvas.getBoundingClientRect();

// 👉 correct scaled click
var x = (click.position.x - rect.left) * (viewer.canvas.width / rect.width);
var y = (click.position.y - rect.top) * (viewer.canvas.height / rect.height);

var pos = viewer.scene.pickPosition(new Cesium.Cartesian2(x, y));
if(!pos){
    var ray = viewer.camera.getPickRay(new Cesium.Cartesian2(x,y));
    pos = viewer.scene.globe.pick(ray, viewer.scene);
}
if(!pos) return;

var c = Cesium.Cartographic.fromCartesian(pos);

var lat = Cesium.Math.toDegrees(c.latitude);
var lon = Cesium.Math.toDegrees(c.longitude);
var ray=viewer.camera.getPickRay(m.endPosition);
var pos=viewer.scene.globe.pick(ray,viewer.scene);
if(!pos)return;
var c=Cesium.Cartographic.fromCartesian(pos);
document.getElementById("coordsBar").innerHTML=
"LAT "+Cesium.Math.toDegrees(c.latitude).toFixed(4)+
" | LON "+Cesium.Math.toDegrees(c.longitude).toFixed(4);
},Cesium.ScreenSpaceEventType.MOUSE_MOVE);


// CLICK SCAN
viewer.screenSpaceEventHandler.setInputAction(function(click){

var ray=viewer.camera.getPickRay(click.position);
var pos=viewer.scene.globe.pick(ray,viewer.scene);
if(!pos)return;

var c=Cesium.Cartographic.fromCartesian(pos);
var lat=Cesium.Math.toDegrees(c.latitude);
var lon=Cesium.Math.toDegrees(c.longitude);
var key = lat.toFixed(4)+"_"+lon.toFixed(4)

if(markerMap[key]){

viewer.entities.remove(markerMap[key])
delete markerMap[key]

return

}

document.getElementById("loader").style.display="block";

// RADAR CIRCLE LOADER

var radius = 5;

var loader = viewer.entities.add({

position: Cesium.Cartesian3.fromDegrees(lon,lat),

ellipse:{
semiMajorAxis: new Cesium.CallbackProperty(function(){
return radius;
}, false),

semiMinorAxis: new Cesium.CallbackProperty(function(){
return radius;
}, false),

material: Cesium.Color.CYAN.withAlpha(0.5),

outline:true,
outlineColor:Cesium.Color.WHITE

}

});

// PULSE ANIMATION

var pulse = viewer.clock.onTick.addEventListener(function(){

radius += 1;

if(radius > 70){
radius = 2 ;
}

});

// SCAN TEXT

var scanText = viewer.entities.add({

position: Cesium.Cartesian3.fromDegrees(lon,lat),

label:{

text:"SCANNING TERRAIN",

font:"14px monospace",

fillColor:Cesium.Color.CYAN,

outlineColor:Cesium.Color.BLACK,

outlineWidth:2,

pixelOffset:new Cesium.Cartesian2(0,-40)

}

})



fetch(window.location.origin + `/data?lat=${lat}&lon=${lon}`)
.then(r=>r.json())
.then(d=>{
viewer.entities.remove(loader)
viewer.clock.onTick.removeEventListener(pulse)
viewer.entities.remove(scanText)

document.getElementById("loader").style.display="none";

viewer.camera.flyTo({
destination:Cesium.Cartesian3.fromDegrees(lon,lat,2500)
});

var entity=viewer.entities.add({
position:Cesium.Cartesian3.fromDegrees(lon,lat),
point:{
pixelSize:16,
color:Cesium.Color.fromCssColorString(d.color),
outlineColor:Cesium.Color.WHITE,
outlineWidth:2
},
label:{
text:
d.place+"\\n\\n"+
" LANDSLIDE RISK: "+d.risk+" ("+d.prob+"%)\\n"+

"NDVI: "+d.ndvi+"\\n"+
"RAIN(6h): "+d.rain_hour+" mm\\n"+
"ELEV: "+d.elev+" m\\n"+
"TERRAIN: "+d.terrain+"\\n"+
"RAIN(24h): "+d.rain+" mm ("+d.rain_type+")\\n"+
"SLOPE: "+d.slope+"°\\n"+
"SOIL: "+d.soil+"\\n"+
"QUAKES: "+d.quakes+"\\n"+
"FUTURE RISK:"+(d.future && d.future.length ? d.future[0].risk : "N/A")+"%\\n"+
"FLOOD: "+d.flood,
font:"13px monospace",
fillColor:Cesium.Color.WHITE,
showBackground:true,
backgroundColor:Cesium.Color.fromCssColorString(d.color).withAlpha(0.7),
horizontalOrigin:Cesium.HorizontalOrigin.LEFT,
verticalOrigin:Cesium.VerticalOrigin.BOTTOM,
pixelOffset:new Cesium.Cartesian2(15,-15)
}
});
markerMap[key]=entity
markers.push(entity)




if(markers.length>0){
document.getElementById("clearBtn").style.display="block"
}

})

},Cesium.ScreenSpaceEventType.LEFT_CLICK)

document.getElementById("clearBtn").onclick=function(){
markers.forEach(m=>viewer.entities.remove(m));
markers=[];
markerMap={};
this.style.display="none";
};

function scaleApp() {

    let baseWidth = 1920;
    let baseHeight = 1080;

    // 📱 if phone vertical → swap dimensions
    if (window.innerHeight > window.innerWidth) {
        baseWidth = 1080;
        baseHeight = 1920;
    }

    let scaleX = window.innerWidth / baseWidth;
    let scaleY = window.innerHeight / baseHeight;

    let scale = Math.min(scaleX, scaleY);

    document.getElementById("app").style.transform =
        "scale(" + scale + ")";
}

window.addEventListener("resize", scaleApp);
window.onload = scaleApp;
</script>
</div>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(html.replace("%TOKEN%", TOKEN))

@app.route("/data")
def data():
    lat=float(request.args.get("lat"))
    lon=float(request.args.get("lon"))
    return jsonify(calculate_risk(lat,lon))


@app.route("/lite")
def lite():
    return """
    <html>
    <body style="background:black;color:white;text-align:center;margin-top:50%">
    <h2>⚠️ Low Device Mode</h2>
    <p>Simple version loaded</p>
    </body>
    </html>
    """

@app.route("/weather")
def weather():

    lat=float(request.args.get("lat"))
    lon=float(request.args.get("lon"))

    return jsonify(weather_forecast(lat,lon))
    
import os

if __name__=="__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
