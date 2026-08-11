import { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant: "primary" | "secondary";
  children: ReactNode;
  className?: string;
}

export function Button({
  variant,
  children,
  className = "",
  ...props
}: ButtonProps) {
  const baseStyles =
    "px-4 py-2 rounded-xl text-sm font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed";
  const variantStyles =
    variant === "primary"
      ? "bg-amber-500 text-neutral-900"
      : "border border-neutral-600 text-neutral-200";

  return (
    <button
      className={`${baseStyles} ${variantStyles} ${className}`.trim()}
      {...props}
    >
      {children}
    </button>
  );
}

export default Button;
