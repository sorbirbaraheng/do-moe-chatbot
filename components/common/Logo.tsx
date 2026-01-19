/**
 * MOE - One Logo Component
 * Reusable logo with mascot image
 */

import React from 'react';

interface LogoProps {
    size?: 'sm' | 'md' | 'lg' | 'xl';
    showText?: boolean;
    textClassName?: string;
    onClick?: () => void;
    className?: string;
}

const SIZES = {
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12',
    xl: 'w-16 h-16',
} as const;

const Logo: React.FC<LogoProps> = ({
    size = 'md',
    showText = true,
    textClassName = '',
    onClick,
    className = '',
}) => {
    const sizeClass = SIZES[size];

    const content = (
        <>
            <div className={`${sizeClass} rounded-xl overflow-hidden shadow-md flex-shrink-0`}>
                <img
                    src="/do-mascot.png"
                    alt="DO - MOE One"
                    className="w-full h-full object-cover"
                />
            </div>
            {showText && (
                <span className={`font-bold tracking-tight ${textClassName}`}>
                    MOE - One
                </span>
            )}
        </>
    );

    if (onClick) {
        return (
            <button
                onClick={onClick}
                className={`flex items-center gap-3 cursor-pointer group hover:opacity-90 transition-opacity ${className}`}
            >
                {content}
            </button>
        );
    }

    return (
        <div className={`flex items-center gap-3 ${className}`}>
            {content}
        </div>
    );
};

export default Logo;
