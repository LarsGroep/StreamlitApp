export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        lofi: {
          bg:      '#0d0d0d',
          surface: '#1a1a1a',
          border:  '#2a2a2a',
          accent:  '#e8ff47',   // LOFI yellow-green
          text:    '#f0f0f0',
          muted:   '#888888',
        },
      },
    },
  },
  plugins: [],
}
