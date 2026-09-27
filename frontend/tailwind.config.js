/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#151B23',
        'primary-dark': '#1E2732',
        text: '#12181F',
        bg: '#F2F4F5',
        shell: '#151B23',
        'shell-2': '#1E2732',
        ground: '#F2F4F5',
        surface: '#FFFFFF',
        border: '#E2E5E9',
        muted: '#5C6773',
        accent: '#F59E0B', 
        open: '#0E7C52',
        closed: '#98A2B0',
        incident: '#B42318',
        'soft-warning': '#FDF0D5',
        ink: '#12181F',
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: {
        card: '8px',
        btn: '6px',
        field: '4px',
      }
    },
  },
  plugins: [],
}
