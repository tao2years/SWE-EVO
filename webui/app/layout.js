import "./globals.css";

export const metadata = {
  title: "SWE-EVO Run Observatory",
  description: "Official48 benchmark dashboard for SWE-EVO runs.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
