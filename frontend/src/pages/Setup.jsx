import Header from '../components/Header';

const steps = [
  {
    number: 1,
    title: 'Create your account',
    description:
      'Create your EasyForm account to access the dashboard and manage personal tokens.',
    img: '/register.png', // Placeholder - final asset can live in /public/images
    cta: {
      label: 'Go to registration',
      href: '/register',
      type: 'internal',
    },
  },
  {
    number: 2,
    title: 'Generate a token',
    description:
      'Create a personal API token inside the dashboard. Store it safely - you will need it inside the add-on.',
    img: '/token.png', // Placeholder - final asset can live in /public/images
    cta: {
      label: 'Open dashboard',
      href: '/dashboard',
      type: 'internal',
    },
  },
  {
    number: 3,
    title: 'Install the add-on',
    description:
      'Install the EasyForm browser add-on from the releases page. Follow the browser instructions to finish the setup.',
    img: '/extension.png', // Placeholder - final asset can live in /public/images
    cta: {
      label: 'View releases',
      href: 'https://github.com/M4RKUS28/EasyForm/releases',
      type: 'external',
    },
  },
  {
    number: 4,
    title: 'Add the token to the add-on',
    description:
      'Open the add-on settings and paste your API token. Save - done! EasyForm can now autofill your forms.',
    img: '/settings.png', // Placeholder - final asset can live in /public/images
  },
];

const StepCard = ({ step }) => {
  const isExternal = step.cta?.type === 'external';
  const CTA = step.cta ? (
    isExternal ? (
      <a
        href={step.cta.href}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors"
      >
        {step.cta.label}
        <span aria-hidden>↗</span>
      </a>
    ) : (
      <a
        href={step.cta.href}
        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600 transition-colors"
      >
        {step.cta.label}
      </a>
    )
  ) : null;

  return (
    <div className="bg-white/90 dark:bg-slate-900/90 rounded-xl overflow-hidden border border-gray-100 dark:border-slate-800 shadow-sm">
      <div className="aspect-video bg-gray-100 dark:bg-slate-800 flex items-center justify-center relative">
        {/* Placeholder image */}
        <img
          src={step.img}
          alt={`${step.title} - step ${step.number}`}
          className="w-full h-full object-cover"
          onError={(e) => {
            // Fallback if the placeholder asset does not exist yet
            e.currentTarget.style.display = 'none';
          }}
        />
        <div className="absolute opacity-40 text-6xl font-bold select-none">
          {step.number}
        </div>
      </div>
      <div className="p-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-9 h-9 flex items-center justify-center rounded-full bg-blue-600 text-white dark:bg-blue-500 text-sm font-semibold">
            {step.number}
          </div>
          <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">
            {step.title}
          </h3>
        </div>
        <p className="text-gray-700 dark:text-gray-300 mb-4">{step.description}</p>
        {CTA}
      </div>
    </div>
  );
};

const Setup = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-100 to-blue-200 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950 transition-colors duration-300">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
        <section className="text-center mb-10 sm:mb-14">
          <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-3">
            EasyForm setup in 4 steps
          </h1>
          <p className="text-gray-700 dark:text-gray-300 max-w-2xl mx-auto">
            Get ready in just a few minutes: create your account, generate a token, install the add-on, and add your token inside the add-on settings.
          </p>
        </section>

        <section className="grid gap-6 md:gap-8 md:grid-cols-2">
          {steps.map((s) => (
            <StepCard key={s.number} step={s} />
          ))}
        </section>

        <section className="mt-12 text-center">
          <p className="text-gray-700 dark:text-gray-300 mb-4">
            Need help? Read the documentation or reach out to us.
          </p>
          <div className="flex gap-3 justify-center">
            <a
              href="/"
              className="px-4 py-2 rounded-lg border border-gray-300 dark:border-slate-700 text-gray-700 dark:text-gray-200 hover:bg-white/70 dark:hover:bg-slate-800/70"
            >
              Back to home
            </a>
            <a
              href="https://github.com/M4RKUS28/EasyForm/releases"
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-600"
            >
              Download add-on
            </a>
          </div>
        </section>
      </main>
    </div>
  );
};

export default Setup;
