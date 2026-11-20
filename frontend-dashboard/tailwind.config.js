/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        optimo: '#16a34a',
        alerta: '#eab308',
        critico: '#dc2626',
        referencia: '#64748b',
      },
    },
  },
  plugins: [],
}
