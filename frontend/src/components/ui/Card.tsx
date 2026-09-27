import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

const Card: React.FC<CardProps> = ({ children, className = '', ...props }) => {
  return (
    <div className={`rounded-card bg-surface border border-border p-4 ${className}`} {...props}>
      {children}
    </div>
  );
};

export default Card;
