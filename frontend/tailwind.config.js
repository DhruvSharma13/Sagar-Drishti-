/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'ocean-dark': '#060D1B',
        'ocean-navy': '#0A1930',
        'ocean-card': '#0E2240',
        'ocean-border': '#1E3A8A',
        'india-saffron': '#FF9933',
        'india-green': '#138808',
        'india-blue': '#000080',
      },
    },
  },
  plugins: [],
};
