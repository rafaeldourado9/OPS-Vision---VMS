/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:       'var(--bg)',
        surface:  'var(--surface)',
        elevated: 'var(--elevated)',
        border:   'var(--border)',
        accent:   'var(--accent)',
        't1':     'var(--text-1)',
        't2':     'var(--text-2)',
        't3':     'var(--text-3)',
        success:  'var(--success)',
        warning:  'var(--warning)',
        danger:   'var(--danger)',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.15s ease-out',
        'slide-in': 'slideIn 0.2s ease-out',
      },
      keyframes: {
        fadeIn:  { from: { opacity: '0' },                   to: { opacity: '1' } },
        slideIn: { from: { opacity: '0', transform: 'translateY(4px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
