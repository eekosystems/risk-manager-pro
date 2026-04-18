import { Route, Routes } from "react-router-dom";

import { LoginPage } from "@/components/auth/login-page";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { ChatPage } from "@/components/chat/chat-page";
import { AppLayout } from "@/components/layout/app-layout";
import { ErrorBoundary } from "@/components/ui/error-boundary";

export function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <AppLayout>
                {({
                  activeFunction,
                  conversationId,
                  setConversationId,
                  onStartChat,
                }) => (
                  <ChatPage
                    activeFunction={activeFunction}
                    conversationId={conversationId}
                    setConversationId={setConversationId}
                    onStartChat={onStartChat}
                  />
                )}
              </AppLayout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </ErrorBoundary>
  );
}
