from google import genai
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import os
import requests

load_dotenv()
api_key = os.getenv("OPENWEATHER_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=gemini_key)

st.title("WeatherGPT")

city = st.text_input("Enter city name:")

if st.button("Get Weather"):
    if city.strip() == "":
        st.session_state["data_ready"] = False
        st.write("Please enter a city name.")
    else:
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={api_key}"
        geo_response = requests.get(geo_url)
        geo_data = geo_response.json()

        if len(geo_data) > 0:
            lat = geo_data[0]["lat"]
            lon = geo_data[0]["lon"]

            nasa_url = f"https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=T2M,PRECTOTCORR&community=RE&longitude={lon}&latitude={lat}&format=JSON"
            nasa_response = requests.get(nasa_url)
            nasa_data = nasa_response.json()

            if nasa_response.status_code == 200 and "properties" in nasa_data:
                monthly_temp = nasa_data["properties"]["parameter"]["T2M"]
                monthly_rain = nasa_data["properties"]["parameter"]["PRECTOTCORR"]

                url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
                response = requests.get(url)
                data = response.json()

                if response.status_code == 200:
                    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric"
                    forecast_response = requests.get(forecast_url)
                    forecast_data = forecast_response.json()

                    aqi_url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={api_key}"
                    aqi_response = requests.get(aqi_url)
                    aqi_data = aqi_response.json()

                    st.session_state["data_ready"] = True
                    st.session_state["city"] = city
                    st.session_state["lat"] = lat
                    st.session_state["lon"] = lon
                    st.session_state["monthly_temp"] = monthly_temp
                    st.session_state["monthly_rain"] = monthly_rain
                    st.session_state["temperature"] = data["main"]["temp"]
                    st.session_state["weather_description"] = data["weather"][0]["description"]
                    st.session_state["humidity"] = data["main"]["humidity"]
                    st.session_state["forecast_data"] = forecast_data
                    st.session_state["aqi_data"] = aqi_data
                else:
                    st.session_state["data_ready"] = False
                    st.write("City not found. Please check the spelling and try again.")
            else:
                st.session_state["data_ready"] = False
                st.write("Climate data unavailable for this location right now. Please try again later.")
        else:
            st.session_state["data_ready"] = False
            st.write("City not found. Please check the spelling and try again.")

if st.session_state.get("data_ready"):
    city = st.session_state["city"]
    lat = st.session_state["lat"]
    lon = st.session_state["lon"]
    monthly_temp = st.session_state["monthly_temp"]
    monthly_rain = st.session_state["monthly_rain"]
    temperature = st.session_state["temperature"]
    weather_description = st.session_state["weather_description"]
    humidity = st.session_state["humidity"]
    forecast_data = st.session_state["forecast_data"]
    aqi_data = st.session_state["aqi_data"]

    month_order = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

    temp_df = pd.DataFrame({"Month": month_order, "Temperature": [monthly_temp[m] for m in month_order]})
    temp_df["Month"] = pd.Categorical(temp_df["Month"], categories=month_order, ordered=True)
    temp_df = temp_df.set_index("Month")

    rain_df = pd.DataFrame({"Month": month_order, "Rainfall": [monthly_rain[m] for m in month_order]})
    rain_df["Month"] = pd.Categorical(rain_df["Month"], categories=month_order, ordered=True)
    rain_df = rain_df.set_index("Month")
    avg_rainfall = sum(monthly_rain.values()) / len(monthly_rain)

    aqi_value = aqi_data["list"][0]["main"]["aqi"]
    aqi_labels = {1: "Good", 2: "Fair", 3: "Moderate", 4: "Poor", 5: "Very Poor"}
    components = aqi_data["list"][0]["components"]

    # 1. Current Weather
    st.write("Current Weather:")
    col1, col2, col3 = st.columns(3)
    col1.metric("Temperature", f"{temperature}°C")
    col2.metric("Condition", weather_description)
    col3.metric("Humidity", f"{humidity}%")

    # 2. 5-Day Forecast
    st.write("5-Day Forecast:")
    forecast_cols = st.columns(5)
    col_index = 0
    for entry in forecast_data["list"]:
        if "12:00:00" in entry["dt_txt"]:
            date = entry["dt_txt"].split(" ")[0]
            temp = entry["main"]["temp"]
            description = entry["weather"][0]["description"]
            forecast_cols[col_index].metric(date, f"{temp}°C", description)
            col_index += 1

    # 3. Historical Climate Charts
    st.write("Average Monthly Temperature (°C):")
    st.bar_chart(temp_df)

    st.write("Average Monthly Rainfall (mm/day):")
    st.bar_chart(rain_df)

    # 4. AQI
    st.write(f"Air Quality Index: {aqi_labels[aqi_value]} ({aqi_value}/5)")

    st.write("Pollutant Levels (μg/m³):")
    pcol1, pcol2, pcol3 = st.columns(3)
    pcol1.metric("PM2.5", components['pm2_5'])
    pcol2.metric("PM10", components['pm10'])
    pcol3.metric("CO", components['co'])

    pcol4, pcol5, pcol6 = st.columns(3)
    pcol4.metric("NO2", components['no2'])
    pcol5.metric("O3", components['o3'])
    pcol6.metric("SO2", components['so2'])

    # 5. Flood Risk Insight
    high_risk_months = [month for month in month_order if monthly_rain[month] > avg_rainfall * 1.5]

    if high_risk_months:
        months_text = ", ".join(high_risk_months)
        st.warning(f"Flood Risk Insight: {months_text} historically see the heaviest rainfall — elevated flood risk during these months.")
    else:
        st.success("Flood Risk Insight: No months show significantly elevated rainfall risk.")

    # 6. Ask Gemini (in sidebar)
    with st.sidebar:
        st.write("### Ask WeatherGPT")
        user_question = st.text_input("Ask a question about this weather/climate data:")

        if user_question:
            context = f"""
            Current weather in {city}: {temperature}°C, {weather_description}, humidity {humidity}%.
            Air Quality Index: {aqi_labels[aqi_value]} ({aqi_value}/5).
            Historical monthly average temperatures: {monthly_temp}.
            Historical monthly average rainfall: {monthly_rain}.
            """

            prompt = f"You are a helpful weather and climate assistant. Using this data:\n{context}\nAnswer this question: {user_question}"

            try:
                gemini_response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=prompt
                )
                st.write(gemini_response.text)
            except Exception as e:
                st.warning("WeatherGPT couldn't generate a response right now — please try asking again in a moment.")
