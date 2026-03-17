/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        vms: {
          bg: '#0f1117',
          sidebar: '#1a1d27',
          card: '#1e2130',
          'card-hover': '#252839',
          border: '#2a2d3a',
          accent: '#3b82f6',
          'accent-hover': '#2563eb',
          success: '#22c55e',
          danger: '#ef4444',
          warning: '#f59e0b',
          info: '#6366f1',
          text: '#ffffff',
          muted: '#9ca3af',
          'muted-dark': '#6b7280',
        },
      },
    },
  },
  plugins: [],
}
