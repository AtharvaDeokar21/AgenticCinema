import CurtainCall from "@/components/CurtainCall";
import Proscenium from "@/components/Proscenium";
import StageDirection from "@/components/StageDirection";
import NavRail from "@/components/NavRail";
import Hero from "@/components/Hero";
import BulbMarquee from "@/components/BulbMarquee";
import NowShowing from "@/components/NowShowing";
import Company from "@/components/Company";
import Slate from "@/components/Slate";
import Reel from "@/components/Reel";
import HouseRules from "@/components/HouseRules";
import Crew from "@/components/Crew";
import TryAgent from "@/components/TryAgent";
import Credits from "@/components/Credits";

export default function Page() {
  return (
    <>
      <CurtainCall />
      <Proscenium />
      <StageDirection />
      <NavRail />

      <main>
        <Hero />
        <BulbMarquee />
        <NowShowing />
        <Company />
        <Slate />
        <Reel />
        <HouseRules />
        <Crew />
        <TryAgent />
      </main>

      <Credits />
    </>
  );
}
