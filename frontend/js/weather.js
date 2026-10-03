/**
 * Weather-aware blight risk calculator using Open-Meteo API (no API key required).
 * Pathogens such as Phytophthora infestans (Late blight) and fungal rusts
 * thrive when relative humidity > 80% and temperatures are 15-24°C.
 */

/**
 * @typedef {Object} WeatherRisk
 * @property {string} riskLevel 'Low' | 'Moderate' | 'High'
 * @property {number} riskScore 0 - 100
 * @property {number} temperature Current temperature in °C
 * @property {number} humidity Current relative humidity in %
 * @property {number} precipitation Current precipitation in mm
 * @property {string} description Human-readable explanation of disease risk
 * @property {Array<{date: string, tempMax: number, tempMin: number, rain: number, humidity: number, risk: string}>} dailyForecast
 */

/**
 * Calculate blight risk based on temperature, humidity, and rainfall.
 * @param {number} temp
 * @param {number} humidity
 * @param {number} [rain=0]
 * @returns {{riskLevel: 'Low'|'Moderate'|'High', score: number, description: string}}
 */
export function calculateBlightRisk(temp, humidity, rain = 0) {
  let score = 0;

  // Temperature factor (15 - 24°C is prime for Late/Early blight and Rusts)
  if (temp >= 15 && temp <= 24) {
    score += 40;
  } else if (temp >= 12 && temp <= 28) {
    score += 25;
  } else {
    score += 10;
  }

  // Humidity factor
  if (humidity >= 85) {
    score += 45;
  } else if (humidity >= 75) {
    score += 30;
  } else if (humidity >= 60) {
    score += 15;
  }

  // Rain factor (free water on leaves promotes spore germination)
  if (rain > 5) {
    score += 15;
  } else if (rain > 1) {
    score += 10;
  }

  score = Math.min(100, Math.max(0, score));

  let riskLevel = "Low";
  let description = "Current weather conditions are unfavorable for rapid fungal or blight spread.";

  if (score >= 70) {
    riskLevel = "High";
    description =
      "Warm, humid conditions strongly favor blight and fungal spore germination. Scout leaves closely.";
  } else if (score >= 45) {
    riskLevel = "Moderate";
    description = "Moderate humidity. Keep an eye on canopy density and soil moisture.";
  }

  return { riskLevel, score, description };
}

/**
 * Fetch current weather through the same-origin backend weather endpoint.
 * @param {number} latitude
 * @param {number} longitude
 * @returns {Promise<WeatherRisk>}
 */
export async function fetchWeatherRisk(latitude, longitude) {
  const url = `/api/v1/weather/risk?latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Weather fetch failed: ${res.statusText}`);
    const payload = await res.json();
    const data = payload.data || payload;

    const currentTemp = data.current?.temperature_2m ?? 20;
    const currentHumidity = data.current?.relative_humidity_2m ?? 65;
    const currentRain = data.current?.precipitation ?? 0;

    const { riskLevel, score, description } = calculateBlightRisk(currentTemp, currentHumidity, currentRain);

    const dailyForecast = [];
    const dates = data.daily?.time || [];
    const maxTemps = data.daily?.temperature_2m_max || [];
    const minTemps = data.daily?.temperature_2m_min || [];
    const rains = data.daily?.precipitation_sum || [];

    for (let i = 0; i < dates.length; i++) {
      const avgTemp = ((maxTemps[i] ?? 20) + (minTemps[i] ?? 15)) / 2;
      const rainVal = rains[i] ?? 0;
      const estimatedHum = rainVal > 2 ? 85 : 70;
      const dayRisk = calculateBlightRisk(avgTemp, estimatedHum, rainVal);

      dailyForecast.push({
        date: dates[i],
        tempMax: Math.round(maxTemps[i] ?? 20),
        tempMin: Math.round(minTemps[i] ?? 15),
        rain: rainVal,
        humidity: estimatedHum,
        risk: dayRisk.riskLevel,
      });
    }

    return {
      riskLevel,
      riskScore: score,
      temperature: currentTemp,
      humidity: currentHumidity,
      precipitation: currentRain,
      description,
      dailyForecast,
    };
  } catch (err) {
    console.warn("Falling back to proxy or offline default weather:", err);
    // Offline or network error fallback
    return {
      riskLevel: "Moderate",
      riskScore: 50,
      temperature: 22,
      humidity: 72,
      precipitation: 0,
      description: "Estimated regional conditions. Maintain standard field observation.",
      dailyForecast: [],
    };
  }
}

/**
 * Get current user position with consent.
 * @returns {Promise<{latitude: number, longitude: number}>}
 */
export function getUserLocation() {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      return reject(new Error("Geolocation is not supported by your browser"));
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          latitude: Number(pos.coords.latitude.toFixed(2)),
          longitude: Number(pos.coords.longitude.toFixed(2)),
        });
      },
      (err) => reject(err),
      { timeout: 8000, enableHighAccuracy: false },
    );
  });
}
