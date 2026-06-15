import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

export default function GrowthChart({ data, dataKey = 'value', label = '' }) {
  if (!data?.length) return (
    <div className="h-32 flex items-center justify-center text-lofi-muted text-xs">
      No history yet
    </div>
  )

  return (
    <div className="h-32">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
          <XAxis dataKey="date" hide />
          <YAxis hide />
          <Tooltip
            contentStyle={{ background: '#1a1a1a', border: '1px solid #2a2a2a', borderRadius: 4 }}
            labelStyle={{ color: '#888' }}
            itemStyle={{ color: '#e8ff47' }}
            formatter={(v) => [v?.toFixed(1), label]}
          />
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke="#e8ff47"
            strokeWidth={1.5}
            dot={false}
            activeDot={{ r: 3, fill: '#e8ff47' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
