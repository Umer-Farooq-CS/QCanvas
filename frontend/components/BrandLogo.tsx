/**
 * The QCanvas logo: gradient mark + gradient wordmark.
 * Used everywhere the brand appears (site navbar, auth pages, footer, IDE menu
 * bar) so the product never shows two different logos.
 */
export default function BrandLogo({
  size = "md",
  wordmark = true,
  className = "",
}: Readonly<{
  size?: "sm" | "md" | "lg";
  wordmark?: boolean;
  className?: string;
}>) {
  const mark = { sm: "h-6 w-6", md: "h-7 w-7", lg: "h-9 w-9" }[size];
  const text = { sm: "text-[1rem]", md: "text-[1.0625rem]", lg: "text-xl" }[size];

  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span className={`qc-brand-mark ${mark}`} aria-hidden="true" />
      {wordmark && (
        <span
          className={`qc-brand-text font-display font-semibold tracking-tight ${text}`}
        >
          QCanvas
        </span>
      )}
    </span>
  );
}
