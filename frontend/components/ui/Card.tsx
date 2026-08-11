import { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
}

export function Card({ children, className = "" }: CardProps) {
  return (
    <div className={`bg-neutral-900 rounded-2xl ${className}`.trim()}>
      {children}
    </div>
  );
}

export default Card;
