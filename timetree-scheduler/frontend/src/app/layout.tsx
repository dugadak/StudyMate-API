import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import { Providers } from './providers'
import { Header } from '@/components/layout/header'
import { Toaster } from '@/components/ui/toast'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: {
    default: 'TimeTree Scheduler',
    template: '%s | TimeTree Scheduler',
  },
  description: '자연어로 일정을 입력하면 AI가 파싱하여 TimeTree 캘린더에 자동 등록하는 서비스',
  keywords: [
    'TimeTree',
    '일정관리',
    'AI',
    '자연어처리',
    '캘린더',
    '일정등록',
    'Claude AI',
  ],
  authors: [
    {
      name: 'TimeTree Scheduler Team',
    },
  ],
  creator: 'TimeTree Scheduler',
  openGraph: {
    type: 'website',
    locale: 'ko_KR',
    url: 'https://timetree-scheduler.com',
    title: 'TimeTree Scheduler',
    description: '자연어로 일정을 입력하면 AI가 파싱하여 TimeTree 캘린더에 자동 등록하는 서비스',
    siteName: 'TimeTree Scheduler',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'TimeTree Scheduler',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'TimeTree Scheduler',
    description: '자연어로 일정을 입력하면 AI가 파싱하여 TimeTree 캘린더에 자동 등록하는 서비스',
    images: ['/og-image.png'],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  manifest: '/manifest.json',
  icons: {
    icon: '/favicon.ico',
    shortcut: '/favicon-16x16.png',
    apple: '/apple-touch-icon.png',
  },
  viewport: {
    width: 'device-width',
    initialScale: 1,
    maximumScale: 1,
  },
  verification: {
    // google: 'google-verification-code',
    // yandex: 'yandex-verification-code',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html 
      lang="ko" 
      className={`${inter.variable} ${jetbrainsMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <meta name="color-scheme" content="light dark" />
        <meta name="theme-color" content="#0ea5e9" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="TimeTree Scheduler" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="msapplication-TileColor" content="#0ea5e9" />
        <meta name="msapplication-config" content="/browserconfig.xml" />
      </head>
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>
          <div className="relative flex min-h-screen flex-col">
            <Header />
            <main className="flex-1">
              {children}
            </main>
          </div>
          <Toaster />
        </Providers>
      </body>
    </html>
  )
}