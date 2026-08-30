import type { Config } from 'tailwindcss'
import animate from 'tailwindcss-animate'

const gold = {
  DEFAULT: 'hsl(38 92% 55%)',
  soft: 'hsl(38 92% 62%)',
  muted: 'hsl(38 30% 40%)',
}

export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        // 「放映室」深暖底色：比纯黑暖、比灰蓝具体。gold 是唯一强调色，
        // 只出现在评级/筛选/计数。其余全部中性，让媒体缩略图当视觉主角。
        gold,
        ink: {
          bg: 'hsl(220 12% 8%)',
          surface: 'hsl(220 10% 11%)',
          raised: 'hsl(220 9% 15%)',
          line: 'hsl(220 8% 22%)',
        },
        steam: {
          DEFAULT: 'hsl(40 20% 88%)',
          dim: 'hsl(40 12% 62%)',
        },
        destructive: 'hsl(0 72% 51%)',
      },
      fontFamily: {
        display: ['"Sora Variable"', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
        mono: ['"SF Mono"', '"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        // 轻微圆角 + 一点圆润，不套满屏圆角胶囊
        card: '14px',
      },
      boxShadow: {
        glow: '0 0 0 1px hsl(38 92% 55% / 0.35), 0 8px 30px -12px hsl(38 92% 55% / 0.25)',
      },
    },
  },
  plugins: [animate],
} satisfies Config