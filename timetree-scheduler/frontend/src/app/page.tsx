'use client'

import { useEffect, useState } from 'react'
import { ChatInterface } from '@/components/chat/chat-interface'
import { Sidebar } from '@/components/layout/sidebar'
import { useAuth } from '@/hooks/use-auth'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { MessageSquare, Calendar, Zap, Shield, Globe, Users } from 'lucide-react'

export default function HomePage() {
  const { user, isLoading } = useAuth()
  const [isMounted, setIsMounted] = useState(false)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  if (!isMounted || isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center space-y-4">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">로딩 중...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <LandingPage />
  }

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <Sidebar />
      <div className="flex-1">
        <ChatInterface />
      </div>
    </div>
  )
}

function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted/20">
      {/* Hero Section */}
      <section className="container mx-auto px-4 pt-20 pb-16">
        <div className="mx-auto max-w-4xl text-center">
          <div className="mb-8 inline-flex items-center rounded-full bg-primary/10 px-4 py-2 text-sm font-medium text-primary">
            🚀 TimeTree와 Claude AI가 만나다
          </div>
          
          <h1 className="mb-6 text-4xl font-bold tracking-tight sm:text-6xl lg:text-7xl">
            자연어로 말하면
            <br />
            <span className="bg-gradient-to-r from-primary to-timetree-600 bg-clip-text text-transparent">
              일정이 완성됩니다
            </span>
          </h1>
          
          <p className="mb-10 text-xl text-muted-foreground sm:text-2xl">
            "내일 오후 2시 팀 회의"라고 말하기만 하면 AI가 알아서 TimeTree 캘린더에 등록해드립니다.
          </p>
          
          <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="lg" className="w-full sm:w-auto">
              <Calendar className="mr-2 h-5 w-5" />
              TimeTree로 시작하기
            </Button>
            
            <Button variant="outline" size="lg" className="w-full sm:w-auto">
              <MessageSquare className="mr-2 h-5 w-5" />
              데모 체험하기
            </Button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="container mx-auto px-4 py-16">
        <div className="mx-auto max-w-6xl">
          <div className="mb-16 text-center">
            <h2 className="mb-4 text-3xl font-bold sm:text-4xl">
              왜 TimeTree Scheduler인가요?
            </h2>
            <p className="text-xl text-muted-foreground">
              복잡한 일정 입력은 이제 그만, 자연스럽게 말하세요.
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            <FeatureCard
              icon={<MessageSquare className="h-8 w-8" />}
              title="자연어 입력"
              description="복잡한 양식 없이 평소 말하는 대로 일정을 입력하세요. '내일 저녁 7시 홍대에서 저녁식사'처럼 자연스럽게요."
            />
            
            <FeatureCard
              icon={<Zap className="h-8 w-8" />}
              title="즉시 파싱"
              description="Claude AI가 날짜, 시간, 장소, 내용을 정확히 이해하고 구조화된 일정으로 변환합니다."
            />
            
            <FeatureCard
              icon={<Calendar className="h-8 w-8" />}
              title="TimeTree 연동"
              description="파싱된 일정을 TimeTree 공유 캘린더에 자동으로 등록하여 팀원들과 실시간 공유합니다."
            />
            
            <FeatureCard
              icon={<Globe className="h-8 w-8" />}
              title="한국어 특화"
              description="'다음주 화요일', '오후', '저녁' 등 한국어 시간 표현을 정확히 이해합니다."
            />
            
            <FeatureCard
              icon={<Shield className="h-8 w-8" />}
              title="안전한 인증"
              description="OAuth 2.0을 통한 안전한 TimeTree 연동과 JWT 기반 사용자 인증을 제공합니다."
            />
            
            <FeatureCard
              icon={<Users className="h-8 w-8" />}
              title="팀 협업"
              description="공유 캘린더를 통해 팀원들과 일정을 실시간으로 공유하고 협업할 수 있습니다."
            />
          </div>
        </div>
      </section>

      {/* Demo Section */}
      <section className="bg-muted/50 py-16">
        <div className="container mx-auto px-4">
          <div className="mx-auto max-w-4xl">
            <div className="mb-16 text-center">
              <h2 className="mb-4 text-3xl font-bold sm:text-4xl">
                이렇게 간단해요
              </h2>
              <p className="text-xl text-muted-foreground">
                자연어 입력부터 캘린더 등록까지 3단계면 완료
              </p>
            </div>

            <div className="grid gap-8 md:grid-cols-3">
              <DemoStep
                step="1"
                title="자연어로 입력"
                description="'내일 오후 3시 치과 예약'"
              />
              
              <DemoStep
                step="2"
                title="AI가 파싱"
                description="날짜, 시간, 내용 자동 추출"
              />
              
              <DemoStep
                step="3"
                title="TimeTree 등록"
                description="확인 후 캘린더에 자동 추가"
              />
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container mx-auto px-4 py-16">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="mb-4 text-3xl font-bold sm:text-4xl">
            지금 바로 시작해보세요
          </h2>
          <p className="mb-8 text-xl text-muted-foreground">
            TimeTree 계정으로 로그인하고 첫 번째 일정을 자연어로 등록해보세요.
          </p>
          
          <Button size="lg" className="w-full sm:w-auto">
            <Calendar className="mr-2 h-5 w-5" />
            TimeTree로 시작하기
          </Button>
        </div>
      </section>
    </div>
  )
}

function FeatureCard({ icon, title, description }: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <Card className="border-0 bg-card/50 backdrop-blur-sm">
      <CardHeader>
        <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
          {icon}
        </div>
        <CardTitle className="text-xl">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <CardDescription className="text-base leading-relaxed">
          {description}
        </CardDescription>
      </CardContent>
    </Card>
  )
}

function DemoStep({ step, title, description }: {
  step: string
  title: string
  description: string
}) {
  return (
    <div className="relative text-center">
      <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full bg-primary text-primary-foreground text-lg font-bold">
        {step}
      </div>
      <h3 className="mb-2 text-lg font-semibold">{title}</h3>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>
  )
}