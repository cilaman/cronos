import { cn } from "../../utils/cn";

interface Props {
  onClose: () => void;
  className?: string;
  children: React.ReactNode;
}

export function Modal({ onClose, className, children }: Props) {
  return (
    <div
      className={cn(
        "fixed inset-0 z-40 flex items-stretch justify-center bg-black/70 p-0 backdrop-blur-sm sm:items-center sm:p-4",
        className,
      )}
      onClick={onClose}
    >
      {children}
    </div>
  );
}
