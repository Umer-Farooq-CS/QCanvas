// QCanvas Project Configuration
// Centralized configuration for all project details, team info, and shared constants
// Import this file in any component to access consistent project information

export interface TeamMember {
  name: string
  team: 'QCanvas' | 'QSim'
  role: string
  bio: string
  email?: string
  github?: string
  linkedin?: string
  image?: string
}

export interface SocialLinks {
  github: string
  discord?: string
  twitter?: string
  linkedin?: string
}

export interface ContactInfo {
  email: string
  support: string
  research: string
  community: string
}

export interface ProjectInfo {
  name: string
  tagline: string
  description: string
  year: number
  version: string
  status: 'development' | 'beta' | 'production'
}

export interface TechnicalSpecs {
  frameworks: string[]
  standards: string[]
  features: string[]
}

// Main project configuration
export const projectConfig: ProjectInfo = {
  name: 'QCanvas',
  tagline: 'Quantum Unified Simulator',
  description: 'A next-generation quantum computing IDE that unifies Cirq, Qiskit, and PennyLane through OpenQASM 3.0. Write quantum code in any framework, compile to OpenQASM, simulate with multiple backends, and visualize results in real-time.',
  year: 2025,
  version: '1.0.0',
  status: 'production'
}

// Team configuration - QCanvas Team
export const qcanvasTeam: TeamMember[] = [
  {
    name: 'Umer Farooq',
    team: 'QCanvas',
    role: 'Core Developer',
    bio: 'Leads the visual editing experience and helps shape the core QCanvas workflow.',
    email: 'umerfarooqcs0891@gmail.com',
    github: 'https://github.com/Umer-Farooq-CS',
    linkedin: 'https://www.linkedin.com/in/umer-farooq-a0838a2a1/',
    image: '/images/team/Umer.jpg'
  },
  {
    name: 'Hussan Waseem Syed',
    team: 'QCanvas',
    role: 'Core Developer',
    bio: 'Focuses on the conversion pipeline and the interactive logic behind QCanvas.',
    email: 'hussainwaseemsyed@gmail.com',
    github: 'https://github.com/hussan-waseem',
    linkedin: 'https://www.linkedin.com/in/hussain-waseem-syed-323948361/',
    image: '/images/team/Hussain.jpg'
  },
  {
    name: 'Muhammad Irtaza Khan',
    team: 'QCanvas',
    role: 'Core Developer',
    bio: 'Works on reliability, integration, and the simulation experience across the app.',
    email: 'muhammadirtazakhan2003@gmail.com',
    github: 'https://github.com/irtaza-khan',
    linkedin: 'https://www.linkedin.com/in/muhammad-irtaza-khan-35589a1b8/',
    image: '/images/team/Irtaza.jpg'
  }
]

// Team configuration - QSim Team
export const qsimTeam: TeamMember[] = [
  {
    name: 'Aneeq Ahmed Malik',
    team: 'QSim',
    role: 'Simulation Research',
    bio: 'Focuses on simulation algorithms and backend execution fidelity.',
    email: 'aneeq.malik@nu.edu.pk',
    github: 'https://github.com/aneeq-malik',
    linkedin: 'https://linkedin.com/in/aneeq-malik'
  },
  {
    name: 'Abeer Noor',
    team: 'QSim',
    role: 'Simulation Research',
    bio: 'Works on circuit interpretation and result visualization workflows.',
    email: 'abeer.noor@nu.edu.pk',
    github: 'https://github.com/abeernoor05',
    linkedin: 'https://www.linkedin.com/in/abeernoor/'
  },
  {
    name: 'Abdullah Mehmood',
    team: 'QSim',
    role: 'Simulation Research',
    bio: 'Supports integration, testing, and simulator reliability across modules.',
    email: 'abdullah.mehmood@nu.edu.pk',
    github: 'https://github.com/NoOne619',
    linkedin: 'https://www.linkedin.com/in/abdullah-mehmood-12548a228/'
  }
]

// Combined team configuration
export const teamConfig: TeamMember[] = [...qcanvasTeam, ...qsimTeam]

// Social and community links
export const socialLinks: SocialLinks = {
  github: 'https://github.com/Umer-Farooq-CS/QCanvas',
  discord: 'https://discord.gg/qcanvas',
  twitter: 'https://twitter.com/qcanvas_dev',
  linkedin: 'https://linkedin.com/company/qcanvas'
}

// Contact information
export const contactInfo: ContactInfo = {
  email: 'team@qcanvas.dev',
  support: 'support@qcanvas.dev',
  research: 'research@qcanvas.dev',
  community: 'community@qcanvas.dev'
}

// Technical specifications
export const technicalSpecs: TechnicalSpecs = {
  frameworks: ['Qiskit (IBM)', 'Cirq (Google)', 'PennyLane (Xanadu)', 'OpenQASM 3.0'],
  standards: ['OpenQASM 3.0', 'Iteration I & II Features', 'QSim Integration'],
  features: [
    'Multi-Framework Compilation',
    'AST-Based Code Parsing',
    'Real-time QSim Simulation',
    'Monaco Web IDE',
    '25+ Quantum Examples',
    'OpenQASM 3.0 Standard',
    'Histogram Visualization',
    'Circuit Statistics',
    'Multiple Sim Backends',
    'If-Else Control Flow',
    'For Loop Support',
    'Quantum Teleportation',
    'Deutsch-Jozsa',
    'Grover\'s Search',
    'QML XOR Classifier'
  ]
}

// Project URLs and paths
export const projectUrls = {
  homepage: '/',
  app: '/app',
  login: '/login',
  docs: '/docs',
  examples: '/examples',
  about: '/about',
  api: '/api'
}

// Initiative information
export const initiativeInfo = {
  name: 'Open Quantum Workbench',
  tagline: 'A FAST University Initiative'
}

// Supervisor information
export const supervisors = [
  {
    name: 'Dr. Imran Ashraf',
    role: 'Project Supervisor',
    email: 'iimran.aashraf@gmail.com',
    github: 'https://github.com/imranashraf',
    linkedin: 'https://www.linkedin.com/in/iimranaashraf/'
  },
  {
    name: 'Dr. Muhammad Nouman Noor',
    role: 'Co-Supervisor',
    // TODO: add Dr. Nouman's real address (this previously held a student's email).
    email: '',
    github: 'https://github.com/noumannoor',
    linkedin: 'https://www.linkedin.com/in/muhammad-nouman-noor-phd-266644a2/'
  }
]

// Project metrics and stats
export const projectStats = {
  frameworks: '3+',
  standards: 'OpenQASM 3.0',
  simulations: 'Real-time',
  examples: '25+',
  gates: '50+',
  backends: '3'
}

// SEO and meta information
export const seoConfig = {
  title: `${projectConfig.name} - ${projectConfig.tagline}`,
  description: projectConfig.description,
  keywords: [
    'quantum computing',
    'qiskit',
    'cirq',
    'pennylane',
    'quantum simulation',
    'quantum circuits',
    'quantum development',
    'quantum education',
    'openqasm'
  ],
  authors: teamConfig.map(member => ({ name: member.name })),
  creator: projectConfig.name,
  publisher: initiativeInfo.name
}

// Navigation menu configuration
export const navigationMenu = [
  { name: 'Home', path: projectUrls.homepage, icon: 'Home' },
  { name: 'Examples', path: projectUrls.examples, icon: 'Play' },
  { name: 'Documentation', path: projectUrls.docs, icon: 'BookOpen' },
  { name: 'About', path: projectUrls.about, icon: 'Info' }
]

// Footer links configuration
export const footerLinks = {
  platform: [
    { name: 'Editor', path: projectUrls.app },
    { name: 'Examples', path: projectUrls.examples },
    { name: 'Documentation', path: projectUrls.docs },
    { name: 'About', path: projectUrls.about }
  ],
  community: [
    { name: 'GitHub', url: socialLinks.github, external: true },
    { name: 'Discord', url: socialLinks.discord, external: true },
    { name: 'Twitter', url: socialLinks.twitter, external: true },
    { name: 'LinkedIn', url: socialLinks.linkedin, external: true }
  ],
  support: [
    { name: 'Contact Team', email: contactInfo.email },
    { name: 'Research', email: contactInfo.research },
    { name: 'Community', email: contactInfo.community },
    { name: 'Support', email: contactInfo.support }
  ]
}

// Helper functions for generating dynamic content
export const getTeamMemberByName = (name: string): TeamMember | undefined => {
  return teamConfig.find(member => member.name === name)
}

export const getTeamByType = (team: 'QCanvas' | 'QSim'): TeamMember[] => {
  return teamConfig.filter(member => member.team === team)
}

export const getFullProjectTitle = (): string => {
  return `${projectConfig.name} - ${projectConfig.tagline}`
}

export const getProjectDescription = (): string => {
  return `${projectConfig.description} Built under ${initiativeInfo.name}: ${initiativeInfo.tagline}.`
}

export const getCopyrightText = (): string => {
  return `© ${projectConfig.year} ${projectConfig.name}. Built for the quantum computing community.`
}

export const getVersionText = (): string => {
  return `Version ${projectConfig.version} (${projectConfig.status})`
}

// Export all configurations as a single object for convenience
export const config = {
  project: projectConfig,
  team: teamConfig,
  qcanvasTeam,
  qsimTeam,
  social: socialLinks,
  contact: contactInfo,
  technical: technicalSpecs,
  urls: projectUrls,
  initiative: initiativeInfo,
  supervisors,
  stats: projectStats,
  seo: seoConfig,
  navigation: navigationMenu,
  footer: footerLinks
}

export default config
