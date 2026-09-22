"""Generate the static research page from reviewed result data and local media."""
from pathlib import Path
from html import escape
import json
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
TABLES=json.loads((ROOT/'scripts/result_data.json').read_text())

def picture(name,alt,eager=False):
    w,h=Image.open(ROOT/'assets/images'/f'{name}.webp').size
    return f'<img src="assets/images/{name}.webp" alt="{escape(alt)}" width="{w}" height="{h}" loading="{"eager" if eager else "lazy"}" decoding="async">'

def figure(name,alt,caption,eager=False):
    return f'<figure class="research-figure"><a href="assets/images/{name}.webp" data-zoom aria-label="Enlarge: {escape(alt)}">{picture(name,alt,eager)}</a><figcaption>{caption}</figcaption></figure>'

def video(name,title,caption='',label='',shape='wide'):
    action='Play overview' if name=='overview' else 'Play video'
    return f'''<figure class="video-figure">
      {f'<h4 class="video-label">{label}</h4>' if label else ''}
      <div class="player {shape}">
        <video preload="none" muted playsinline poster="assets/images/{name}.webp" data-src="assets/videos/{name}.mp4" aria-label="{escape(title)}"></video>
        <button class="play-button" type="button" aria-label="Play {escape(title)}"><span aria-hidden="true">▶</span> {action}</button>
        <p class="video-error" hidden>Video could not load. <a href="assets/videos/{name}.mp4">Open the MP4</a>.</p>
      </div>
      {f'<figcaption>{caption}</figcaption>' if caption else ''}
      <noscript><p><a href="assets/videos/{name}.mp4">Watch {escape(title)}</a></p></noscript>
    </figure>'''

def result(key):
    t=TABLES[key]
    rows=''.join('<tr'+(' class="highlight"' if 'ForesightIL' in r[0] or 'VIP +' in r[0] else '')+'><th scope="row">'+r[0]+'</th>'+''.join('<td>'+v+'</td>' for v in r[1:])+'</tr>' for r in t['rows'])
    return f'''<div class="result" id="result-{key}"><div class="table-scroll" tabindex="0" role="region" aria-label="Scrollable table: {t['title']}"><table><caption>{t['caption']}</caption><thead><tr>{''.join('<th scope="col">'+h+'</th>' for h in t['heads'])}</tr></thead><tbody>{rows}</tbody></table></div><p class="result-note">{t['takeaway']}</p></div>'''

franka_more=''
for name,title,note in [('pp_1','Green bowl to red plate','Successful placement.'),('pp_2','Green bowl to wooden tray','Successful placement.'),('pp_3','Green bowl to wooden tray, second rollout','Successful placement.'),('pp_fail_1','Blue-bowl transport','The bowl tilts during transport and remains away from the tray.'),('pp_fail_2','Green-bowl placement','The recording ends before target placement.')]:
    franka_more+=video('franka-'+name,title,note+' 2× playback.',title,'standard')

sim_videos=''
for stem,title in [('pusht','Push-T'),('libero_goal','LIBERO Goal'),('blockpush','Block Pushing')]:
    sim_videos+=f'<article class="sim-task"><h3>{title}</h3>'+video(stem+'_plan',title+' with planning',label='<span class="method-name">ForesightIL</span>',shape='square')+video(stem+'_no_plan',title+' policy only',label='Diffusion Policy',shape='square')+'</article>'

html=f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="ForesightIL combines imitation policies with latent world-model planning. Robot demonstrations, simulation experiments, and analyses of value learning and planning on demand.">
<meta name="theme-color" content="#ffffff">
<meta property="og:title" content="ForesightIL: Latent World Models Enhance Imitation Learning with Foresight">
<meta property="og:description" content="Robot demonstrations and experiments with policy-guided latent planning.">
<meta property="og:image" content="assets/images/hero.webp"><meta property="og:type" content="website">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="css/site.css"><script src="assets/site.js" defer></script>
<title>ForesightIL: Latent World Models Enhance Imitation Learning with Foresight</title>
</head><body>
<a class="skip-link" href="#main">Skip to content</a>
<header><nav class="nav" aria-label="Page sections"><a class="project-name" href="#intro">ForesightIL</a><a href="#method">Method</a><a href="#simulation">Simulation</a><a href="#robots">Real robots</a><a href="#results">Analysis</a><a href="#overview">Video</a></nav></header>
<main id="main" class="container">
<section id="intro" class="intro">
  <h1><span>ForesightIL:</span> Latent World Models Enhance<br class="desktop-break"> Imitation Learning with Foresight</h1>
  <p class="intro-link"><a class="overview-link" href="#overview"><span aria-hidden="true">▶</span> Video overview · 3 minutes</a></p>
  {figure('hero','ForesightIL overview: policy-guided latent rollouts, goal-value selection, and uncertainty-gated planning.','<strong>ForesightIL plans over imitation-policy proposals.</strong> A latent world model predicts their outcomes, a learned goal value ranks them, and an uncertainty gate decides when to invoke planning.',True)}
  <div class="intro-text"><p>Imitation policies learn useful behaviors from demonstrations, but reactive execution can struggle in long-horizon tasks and unfamiliar states. <strong>ForesightIL</strong> augments an imitation policy with a latent world model and a self-supervised goal value. The policy proposes plausible actions; the world model predicts their consequences; and the value estimates progress toward the goal. A learned uncertainty signal invokes this search on demand.</p></div>
</section>

<section id="method" class="section">
  <h2>Method</h2>
  <p>The policy and world model share visual features, so the policy can be queried on both observed and imagined states. Each candidate trajectory alternates policy sampling with latent prediction. The planner ranks the terminal states by a goal-conditioned value, executes the selected first action chunk, and receives a new observation before the next decision. Image decoding is used only for visualizing predictions.</p>
  <div class="method-text"><p><strong>Goal value.</strong> VIP with temporal straightening learns a representation in which distance to the goal reflects progress. This lets the planner compare trajectories that stop short of task completion.</p><p><strong>Planning gate.</strong> A learned head estimates uncertainty in the dynamics. The uncertainty score divided by its threshold defines the gate: values below one execute the policy proposal; values at or above one invoke candidate search. The threshold controls planning frequency. Predicted model error is a heuristic for allocating search, not a direct estimate of planning benefit.</p></div>
</section>

<section id="simulation" class="section">
  <h2>Simulation Experiments</h2>
  <p>We compare planning with direct policy execution on Push-T, LIBERO Goal, and Block Pushing. Push-T is measured by maximum target coverage, while the other tasks use success rate.</p>
  <article class="task simulation-showcase" id="pusht-gated"><h3>Planning on demand in Push-T</h3>
    <p class="task-description">A single-goal rollout with the trained uncertainty head, world model, and goal value. The blue and amber labels show the controller's actual decisions.</p>
    {video('pusht-gated','Push-T with uncertainty-guided ForesightIL','This rollout finishes at 98.6% target overlap and was selected from eight initial states. The first second uses planning to collect observation history; no uncertainty value is available yet. The trace then shows the measured uncertainty divided by its fixed planning threshold. Playback follows simulation time at 1×.','<span class="method-name">ForesightIL</span> <span class="video-subtitle">WM + BC</span>',shape='gated')}
  </article>
  <h3 class="subsection-title">Simulation comparisons</h3>
  <p class="simulation-guide">These comparison clips are from the original experiments; the table reports the current benchmark results. <strong>Inside each comparison video:</strong> the first (top) row shows the ground-truth environment, the second (bottom) row shows world-model predictions, and the second (right) column shows the goal.</p>
  <div class="sim-grid">{sim_videos}</div>
  <h3 class="subsection-title">Simulation results</h3>{result('simulation')}
</section>

<section id="robots" class="section">
  <h2>Real-Robot Experiments</h2>
  <p>We evaluate multi-stage manipulation with two YAM arms and pick-and-place and block-pushing tasks with a Franka arm. The bimanual demonstrations below each use a single successful ForesightIL rollout. The policy-only clips show separately recorded failure examples.</p>
  <article class="task" id="toy-kitchen"><h3>Toy Kitchen</h3><p class="task-description">Place both toy-food objects in the pot, then put on the lid.</p>
  <div class="video-pair">
    {video('toy-kitchen','Toy Kitchen with ForesightIL','Both food objects reach the pot and the lid is placed.','<span class="method-name">ForesightIL</span> <span class="video-subtitle">WM + BC</span>',shape='gated')}
    {video('toy-kitchen-bc','Toy Kitchen with BC only','<strong>Failure: incomplete sequence.</strong> After placing the first food object, the rollout makes no further progress on the remaining food and lid steps.','BC only',shape='gated')}
  </div>
  <p class="note">The BC clip contains low-rate observation frames at their recorded timing and uses an earlier trained policy. It is an illustrative failure example, not a matched-policy comparison.</p></article>
  <article class="task" id="desk-cleanup"><h3>Long-Horizon Desk Cleanup</h3><p class="task-description">Insert flowers into the vase, hand the dish across and place it in the tray, and put the ring on the stand.</p>
  <div class="video-pair">
    {video('desk-cleanup','Desk Cleanup with ForesightIL','The robot completes all three subtasks, including the dish handover.','<span class="method-name">ForesightIL</span> <span class="video-subtitle">WM + BC</span>',shape='gated')}
    {video('desk-cleanup-bc','Desk Cleanup with BC only','<strong>Failure: missed insertion.</strong> The flowers land beside the vase and remain on the table while the robot continues with later subtasks.','BC only',shape='gated')}
  </div></article>
  <p class="video-legend"><span class="key policy"></span> Model-free policy <span class="key planning"></span> Model-based plan. Mode labels and colored timelines follow the executed action. The trace shows its uncertainty score divided by the planning threshold (plan at ≥ 1), with a moving cursor in recorded time. Playback speed is marked in each clip.</p>
  <h3 class="subsection-title">Real-robot success rates</h3>{result('robots')}
  <article class="task" id="franka"><h3>Franka PickPlace</h3><p class="task-description">Grasp a bowl and place it on a target surface. These recordings are shown at 2× speed.</p><div class="video-pair">
    {video('franka-pp_0','Franka PickPlace with ForesightIL','The blue bowl is lifted and placed on the wooden tray.','<span class="method-name">ForesightIL</span> <span class="video-subtitle">WM + BC</span>','standard')}
    {video('franka-pp_fail_0','Franka PickPlace with BC only','<strong>Failure: unsuccessful grasp.</strong> The gripper withdraws without the blue bowl; placement is not completed.','BC only','standard')}
  </div><details class="additional-clips"><summary>Additional Franka WM + Planning Recordings</summary><div class="archive-grid">{franka_more}</div></details></article>
</section>

<section id="results" class="section">
  <h2>Planning and Value Learning</h2>
  <article class="study"><h3>Planning on demand</h3><p>The controlled gating study compares the same policy, value, and candidate budget within each task. The target planning fraction p is set by threshold calibration; the measured fraction can differ as the controller visits different states.</p>{result('gate')}</article>
  <article class="study"><h3>Goal-value ablation</h3><p>These experiments isolate the score used to rank imagined trajectories. The policy and world model remain fixed.</p>{result('value')}</article>
  <article class="study"><h3>Composing specialized policies</h3><p>Given a goal image, the planner samples from separately trained specialists and ranks their predicted outcomes. The constituent policies remain fixed.</p>{result('composition')}</article>
  <article class="study"><h3>Inference latency</h3><p>A flow-map policy generates actions with one network evaluation, compared with ten for flow matching. The comparison uses the same three-camera inputs, 20-step action chunks, and planning budget.</p>
    <div class="medium-figure">{figure('latency','Server latency for flow-matching and flow-map policies on Toy Kitchen and Desk Cleanup.','Server latency on an NVIDIA L40: bars show medians and caps mark p95. The flow-map policy takes 41.4–41.9 ms for direct decisions and 484.7–498.5 ms for planned decisions. Planned decisions include eight four-step model rollouts.')}</div>
  </article>
</section>

<section id="predictions" class="section">
  <h2>World-Model Predictions</h2>
  <p>Observed frames appear above decoded predictions. After three context observations, the model follows recorded actions without new observations. The first displayed column is the final context frame; frames are aligned at six frames per second.</p>
  {figure('openloop','Observed and predicted frames for Toy Kitchen and Desk Cleanup.','Open-loop predictions on the two bimanual tasks. The decoder is used for visualization, not planning.')}
  <h3 class="subsection-title">Candidate selection during lid transport</h3>
  {figure('candidate_outcomes','Four imagined Toy Kitchen outcomes with action traces and values; candidate c1 is selected.','Candidate c₁ has the highest recorded value (−8.31) and lifts the hand while keeping the gripper closed. Columns show predictions after 20 control steps. Only the selected action chunk is executed.')}
</section>

<section id="analysis" class="section">
  <h2>Additional Experiments</h2>
  <article class="study"><h3>Candidate count and planning horizon</h3><div class="figure-pair">
    {figure('candidate_scaling','Push-T coverage for 1 to 64 candidate trajectories.','<strong>Candidate count.</strong> Coverage rises from 0.719 at N = 1 to 0.810 at N = 32, then is 0.787 at N = 64. The last two settings have overlapping variability; this does not establish a sharp optimum.')}
    {figure('planning_horizon','Push-T coverage for horizons of one to five action chunks.','<strong>Planning horizon.</strong> With N = 32, mean coverage is 0.785 for one imagined chunk, 0.809 for three, and 0.817 for five. Only the first chunk is executed.')}
  </div><p class="note">Single-goal Push-T with VIP and temporal straightening. Error bars show ±1 sample SD across three seeds, with 50 episodes per seed.</p></article>
  <article class="study"><h3>Uncertainty estimation</h3>
    {figure('uncertainty_diagnostics','Error detection by the uncertainty head and realized errors binned by predicted score.','AUROC for detecting the highest-error quartile is 0.907 on single-goal Push-T, 0.957 on multi-goal Push-T, and 0.842 on LIBERO. The diagnostic uses 12 held-out trajectories per environment.')}
    <p class="note">Higher-scoring bins generally have larger realized prediction errors. These are observed transitions, not imagined rollout states. This measures error detection, not the benefit of planning.</p>
  </article>
  <article class="study"><h3>Value geometry</h3><div class="medium-figure">
    {figure('value_geometry','Turning loss and first-principal-component variance with and without temporal straightening.','Across 150 held-out multi-goal Push-T trajectories, straightening reduces turning loss from 1.152 to 1.067 and increases the first-principal-component variance fraction from 0.583 to 0.620. These are aggregate means without uncertainty intervals.')}
  </div></article>
  <article class="study"><h3>Alternative policy backbone and visual robustness</h3>
    {figure('appendix_policy_robustness','VQ-BeT candidate scaling, changed goal colors, and randomized T-object colors.','With VQ-BeT, coverage increases from approximately 0.55 with one candidate to 0.61 with 50. Under changed goal and T-object colors, ForesightIL reaches 0.43 and 0.65 coverage, respectively.')}
    <p class="note">All methods are trained on in-distribution observations. Only means are available; the VQ-BeT curve is reconstructed from the original evaluation plot.</p>
  </article>
  <article class="study"><h3>Additional prediction diagnostics</h3>
    {figure('sim_openloop_comparison','Observed and predicted frames for simulated manipulation tasks.','Open-loop simulation predictions follow recorded actions without new observations. Observations are shown above predictions.')}
    <div class="figure-pair">
      {figure('yam_candidate_outcomes','Original policy samples during Desk Cleanup ring transport and their imagined outcomes.','<strong>Policy samples.</strong> During ring transport, c₁ has the highest recorded value (−13.03). Only the selected sample is executed; the other columns show imagined alternatives.')}
      {figure('yam_action_diagnostics','Controlled action edits during Desk Cleanup and their predicted outcomes.','<strong>Controlled action edits.</strong> Opening the gripper, shifting laterally, and holding position change the predicted outcome. These edited action probes are not additional executed trials or original policy samples.')}
    </div>
  </article>
</section>

<section id="overview" class="section overview-section"><h2>Video Overview</h2><p class="center">A three-minute walkthrough of the method, experiments, and robot demonstrations. No narration.</p>{video('overview','ForesightIL three-minute overview',shape='standard')}</section>
</main>
<footer><a href="#intro">ForesightIL</a><a href="#intro">Back to top ↑</a></footer>
<dialog id="figure-dialog" aria-label="Enlarged research figure"><button type="button" class="dialog-close" aria-label="Close enlarged figure">Close ×</button><img alt=""><p></p></dialog>
</body></html>'''
(ROOT/'index.html').write_text('\n'.join(line.rstrip() for line in html.splitlines())+'\n')
print('Built research page: hero first, visible simulations and results, no paper links or attribution section.')
