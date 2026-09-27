import React from 'react';
import Spinner from './Spinner';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'danger' | 'success' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  fullWidth?: boolean;
}

const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  fullWidth = false,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles = 'inline-flex items-center justify-center font-medium rounded-btn transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed';
  
  const variants = {
    primary: 'bg-accent text-ink hover:bg-accent/90 focus:ring-accent border border-accent',
    danger: 'bg-incident text-surface hover:bg-incident/90 focus:ring-incident border border-incident',
    success: 'bg-open text-surface hover:bg-open/90 focus:ring-open border border-open',
    secondary: 'bg-surface text-ink border border-border hover:bg-ground focus:ring-border',
    ghost: 'bg-transparent text-muted border border-transparent hover:bg-border/50 hover:text-ink focus:ring-border'
  };
  
  const sizes = {
    sm: 'px-3 py-1.5 text-sm min-h-[32px]',
    md: 'px-4 py-2 text-[14px] min-h-[36px]',
    lg: 'px-6 py-3 text-base min-h-[44px]' // Large touch targets para mobile
  };

  const widthClass = fullWidth ? 'w-full' : '';

  return (
    <button
      className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${widthClass} ${className}`}
      disabled={loading || disabled}
      {...props}
    >
      {loading && <Spinner size="sm" className="mr-2" />}
      {children}
    </button>
  );
};

export default Button;
