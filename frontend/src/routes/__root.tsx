import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";

import appCss from "../styles.css?url";

// 존재하지 않는 주소로 접속했을 때 보여주는 404 페이지
function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-foreground">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-foreground">
          Page not found
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="mt-6">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Go home
          </Link>
        </div>
      </div>
    </div>
  );
}

// 페이지 로딩 중 에러가 발생했을 때 보여주는 에러 화면
function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          This page didn't load
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Something went wrong on our end. You can try refreshing or head back home.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              // 라우터 데이터를 다시 불러오고 에러 상태를 초기화
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent"
          >
            Go home
          </a>
        </div>
      </div>
    </div>
  );
}

// 전체 앱의 루트 라우트 설정
export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    // 브라우저 탭 제목, 설명, 공유 정보 같은 메타데이터 설정
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "IntelliCode Compare" },
      {
        name: "description",
        content: "여러 LLM의 코드 응답을 비교하고 검증하는 웹 서비스입니다.",
      },
      { name: "author", content: "Programming 2-1 Team" },
      { property: "og:title", content: "IntelliCode Compare" },
      {
        property: "og:description",
        content: "여러 LLM의 코드 응답을 비교하고 검증하는 웹 서비스입니다.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
      { name: "twitter:title", content: "IntelliCode Compare" },
      {
        name: "twitter:description",
        content: "여러 LLM의 코드 응답을 비교하고 검증하는 웹 서비스입니다.",
      },
    ],
    // 전체 페이지에 적용할 CSS 파일 연결
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
    ],
  }),

  // 전체 HTML 구조와 실제 화면 컴포넌트를 연결
  shellComponent: RootShell,
  component: RootComponent,

  // 잘못된 경로 또는 에러 상황에서 보여줄 컴포넌트 지정
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

// 모든 페이지를 감싸는 가장 바깥쪽 HTML 구조
function RootShell({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <HeadContent />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

// React Query 설정을 전체 페이지에 적용하고, 현재 경로의 페이지를 출력
function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      <Outlet />
    </QueryClientProvider>
  );
}