import Link from "next/link";

export default function NotFound() {
  return (
    <div className="empty" style={{ paddingTop: 96 }}>
      <h3>Page not found</h3>
      <p>This page does not exist in REDUTAX.</p>
      <Link href="/" className="btn btn-secondary">Back to home</Link>
    </div>
  );
}
