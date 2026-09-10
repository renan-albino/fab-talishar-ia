import React from 'react';

interface AdUnitProps {
  placement: string;
  className?: string;
}

export const AdUnit: React.FC<AdUnitProps> = ({
  placement,
  className = ''
}) => {
  return <div className={`ad-unit ${className}`} data-ad={placement} style={{ display: 'none' }} />;
};

export default AdUnit;
