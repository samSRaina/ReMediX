import type { Config } from 'tailwindcss';

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        slate: {
          950: '#020617',
        },
      },
      boxShadow: {
        soft: '0 8px 30px rgba(2, 6, 23, 0.08)',
      },
    },
  },
  plugins: [],
} satisfies Config;

