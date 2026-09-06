import "./globals.css";

export const metadata = {
  title: "School-Fit Copilot",
  description: "Compare two primary schools around your family's requirements, evidence and questions to ask next.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
