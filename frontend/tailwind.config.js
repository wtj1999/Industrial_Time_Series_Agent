/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Industrial-themed brand palette
        brand: {
          50: '#eef4ff',
          100: '#d9e6ff',
          200: '#bcd3ff',
          300: '#8eb6ff',
          400: '#598dff',
          500: '#3366ff',
          600: '#1f47f5',
          700: '#1734e1',
          800: '#192cb6',
          900: '#1a2b8f',
          950: '#141b57',
        },
        steel: {
          50: '#f6f7f9',
          100: '#eceef2',
          200: '#d5dae3',
          300: '#b0b9ca',
          400: '#8493ab',
          500: '#647591',
          600: '#4f5d78',
          700: '#414c62',
          800: '#384053',
          900: '#212635',
          950: '#0f121b',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'PingFang SC',
          'Hiragino Sans GB',
          'Microsoft YaHei',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        mono: [
          'JetBrains Mono',
          'Fira Code',
          'Cascadia Code',
          'Consolas',
          'monospace',
        ],
      },
      boxShadow: {
        soft: '0 2px 12px -2px rgba(15, 18, 27, 0.08), 0 4px 24px -4px rgba(15, 18, 27, 0.06)',
        card: '0 1px 3px rgba(15, 18, 27, 0.05), 0 1px 2px rgba(15, 18, 27, 0.04)',
        glow: '0 0 0 1px rgba(51, 102, 255, 0.15), 0 8px 24px -8px rgba(51, 102, 255, 0.35)',
      },
      animation: {
        'fade-in': 'fadeIn 200ms ease-out',
        'slide-up': 'slideUp 220ms ease-out',
        'pulse-soft': 'pulseSoft 1.6s ease-in-out infinite',
        blink: 'blink 1.2s steps(2, start) infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '0.8' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
};
