import React from 'react';

interface AdRailLayoutProps {
  children: React.ReactNode;
  contentWidth?: number;
}

export const AdRailLayout: React.FC<AdRailLayoutProps> = ({ children }) => {
  return <>{children}</>;
};

export default AdRailLayout;
