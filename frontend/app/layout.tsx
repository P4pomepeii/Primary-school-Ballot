export const metadata = {
  title: "School-Fit Copilot",
  description: "Personalised, explainable primary school recommendations for Singapore parents.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#f7f7f5" }}>
        {children}
      </body>
    </html>
  );
}
