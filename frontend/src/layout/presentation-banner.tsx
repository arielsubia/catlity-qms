import logo from '../assets/logo-phildev.png'
import teclab from '../assets/teclab.png'

// Academic frame only. Drop this component when the product is no longer a final project.
export const PresentationBanner = () => (
  <header className="presentation-banner">
    <p className="presentation-banner-mark">
      <img className="presentation-banner-teclab" src={teclab} alt="Teclab" />
      <span>Trabajo final — Tecnicatura en Cloud Administration</span>
    </p>
    <p className="presentation-banner-credit">
      <img src={logo} alt="" width={22} height={22} />
      Phil Dev
    </p>
  </header>
)
