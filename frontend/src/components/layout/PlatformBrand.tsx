import { Link } from 'react-router-dom';
import './PlatformBrand.css';

export function PlatformBrand() {
  return (
    <Link className="platform-brand" to="/chat" aria-label="工业时序智能体首页">
      <img className="platform-brand-mark" src={`${import.meta.env.BASE_URL}brand/signal-slices.svg`} alt="" width="40" height="30" />
      <span className="platform-brand-copy">
        <strong>工业时序智能体</strong>
        <span lang="en">Industrial Time Series Agent</span>
      </span>
    </Link>
  );
}
