import React from 'react';
import { Category } from '../../types';
import { MOE_COLORS } from '../../constants';

interface CategorySelectorProps {
  selected: Category;
  onSelect: (category: Category) => void;
  disabled?: boolean;
}

const CategorySelector: React.FC<CategorySelectorProps> = ({ selected, onSelect, disabled }) => {
  const tabs = [
    { id: Category.General, label: 'ทั่วไป', icon: '🌍', sublabel: 'ถาม-ตอบทั่วไป' },
    { id: Category.School, label: 'โรงเรียน', icon: '🏫', sublabel: 'ค้นหาโรงเรียน' },
    { id: Category.Student, label: 'นักเรียน', icon: '🎓', sublabel: 'สถิตินักเรียน' },
  ];

  return (
    <div className="w-full mb-4 sm:mb-6 px-1 sm:px-4">
      {/* Segmented Control - Apple 2026 visionOS Style */}
      <div className="bg-black/[0.04] p-1.5 rounded-[18px] flex relative backdrop-blur-xl border border-white/40 shadow-inner">
        {/* Animated Background Indicator with Glow */}
        <div
          className="absolute top-1.5 bottom-1.5 rounded-[14px] shadow-[0_4px_12px_rgba(0,0,0,0.08),0_0_20px_rgba(0,122,255,0.06)] transition-all duration-400 ease-[cubic-bezier(0.34,1.56,0.64,1)] z-0 bg-white/95 backdrop-blur-md"
          style={{
            left: `calc(${(tabs.findIndex(t => t.id === selected) * 100) / tabs.length}% + 4px)`,
            width: `calc(${100 / tabs.length}% - 8px)`
          }}
        />

        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onSelect(tab.id)}
            disabled={disabled}
            className={`
              relative z-10 flex-1 flex flex-col items-center justify-center gap-0.5 
              py-3 sm:py-3.5 px-2 sm:px-3
              rounded-xl 
              text-[12px] sm:text-[13px] font-semibold 
              transition-all duration-300 ease-out
              active:scale-[0.96] touch-manipulation
              min-h-[52px] sm:min-h-[60px]
              ${selected === tab.id
                ? 'text-[#007AFF]'
                : 'text-[#86868B] hover:text-[#1D1D1F]'}
              disabled:opacity-40 disabled:cursor-not-allowed
            `}
          >
            <span className={`
              text-xl sm:text-2xl 
              transition-all duration-300
              ${selected === tab.id ? 'scale-110 grayscale-0 drop-shadow-sm' : 'scale-100 grayscale opacity-60'}
            `}>
              {tab.icon}
            </span>
            <span className="font-semibold tracking-tight">{tab.label}</span>
            {/* Sublabel - hidden on very small screens */}
            <span className={`
              hidden xs:block text-[9px] sm:text-[10px] font-medium
              transition-all duration-300
              ${selected === tab.id ? 'text-[#007AFF]/60' : 'text-[#AEAEB2]'}
            `}>
              {tab.sublabel}
            </span>
          </button>
        ))}
      </div>

      {/* Mobile indicator pill - Apple 2026 Style */}
      <div className="flex justify-center mt-2.5 sm:mt-3">
        <div className="flex items-center gap-2 text-[10px] sm:text-[11px] font-medium text-[#86868B] bg-white/60 backdrop-blur-md px-4 py-1.5 rounded-full shadow-sm border border-white/50">
          <span className="w-1.5 h-1.5 rounded-full bg-[#32D74B] shadow-[0_0_6px_rgba(50,215,75,0.5)] animate-pulse"></span>
          <span>
            {selected === Category.General && "พร้อมตอบคำถามทั่วไป"}
            {selected === Category.School && "พร้อมค้นหาโรงเรียน"}
            {selected === Category.Student && "พร้อมดูสถิตินักเรียน"}
          </span>
        </div>
      </div>
    </div>
  );
};

export default React.memo(CategorySelector);