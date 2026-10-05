'use client';

import { useState, useEffect } from 'react';
import Card from '@/components/ui/Card';
import PowerChart from '@/components/charts/PowerChart';
import { getWeather, getTrends } from '@/lib/data';

export default function WeatherPage() {
  const [weather, setWeather] = useState<any>(null);
  const [irradianceTrend, setIrradianceTrend] = useState<any[]>([]);
  const [tempTrend, setTempTrend] = useState<any[]>([]);

  useEffect(() => {
    getWeather().then(setWeather);
    getTrends('irradiance', 24).then(setIrradianceTrend);
    getTrends('temperature', 24).then(setTempTrend);
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Clima</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card title="Irradiancia"><div className="text-3xl font-bold text-center py-4">{weather?.irradiance_wm2 || '--'} W/m²</div></Card>
        <Card title="Temperatura"><div className="text-3xl font-bold text-center py-4">{weather?.temperature_c || '--'}°C</div></Card>
        <Card title="Umidade"><div className="text-3xl font-bold text-center py-4">{weather?.humidity_pct || '--'}%</div></Card>
        <Card title="Vento"><div className="text-3xl font-bold text-center py-4">{weather?.wind_speed_ms || '--'} m/s</div></Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Irradiancia (24h)"><PowerChart data={irradianceTrend} color="#f59e0b" /></Card>
        <Card title="Temperatura (24h)"><PowerChart data={tempTrend} color="#ef4444" /></Card>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card title="Direcao Vento"><div className="text-2xl font-bold text-center py-4">{weather?.wind_direction_deg || '--'}°</div></Card>
        <Card title="Pressao"><div className="text-2xl font-bold text-center py-4">{weather?.pressure_hpa || '--'} hPa</div></Card>
        <Card title="Precipitacao"><div className="text-2xl font-bold text-center py-4">{weather?.precipitation_mm || '--'} mm</div></Card>
        <Card title="UV Index"><div className="text-2xl font-bold text-center py-4">{weather?.uv_index || '--'}</div></Card>
      </div>
    </div>
  );
}
