const defaultTheme = require('tailwindcss/defaultTheme');
const colors = require('@tailwindcss/ui/colors');
const rgba = require('hex-to-rgba');

module.exports = {
	theme: {
		extend: {
			fontFamily: {
				sans: ['var(--font-family, Inter)', ...defaultTheme.fontFamily.sans]
			},
			colors: {
				primary: {
					'50': `var(--primary-50, ${colors.blue[50]})`,
					'100': `var(--primary-100, ${colors.blue[100]})`,
					'200': `var(--primary-200, ${colors.blue[200]})`,
					'300': `var(--primary-300, ${colors.blue[300]})`,
					'400': `var(--primary-400, ${colors.blue[400]})`,
					'500': `var(--primary-500, ${colors.blue[500]})`,
					'600': `var(--primary-600, ${colors.blue[600]})`,
					'700': `var(--primary-700, ${colors.blue[700]})`,
					'800': `var(--primary-800, ${colors.blue[800]})`,
					'900': `var(--primary-900, ${colors.blue[900]})`
				},
				gray: {
					'50': `var(--gray-50, ${colors.gray[50]})`,
					'100': `var(--gray-100, ${colors.gray[100]})`,
					'200': `var(--gray-200, ${colors.gray[200]})`,
					'300': `var(--gray-300, ${colors.gray[300]})`,
					'400': `var(--gray-400, ${colors.gray[400]})`,
					'500': `var(--gray-500, ${colors.gray[500]})`,
					'600': `var(--gray-600, ${colors.gray[600]})`,
					'700': `var(--gray-700, ${colors.gray[700]})`,
					'800': `var(--gray-800, ${colors.gray[800]})`,
					'900': `var(--gray-900, ${colors.gray[900]})`
				},
				black: '#112B42',
				code: {
					green: '#b5f4a5',
					yellow: '#ffe484',
					purple: '#d9a9ff',
					red: '#ff8383',
					blue: '#93ddfd',
					white: '#fff'
				}
			},
			borderRadius: {
				xl: '0.75rem'
			},
			boxShadow: theme => ({
				'outline-primary': `0 0 0 3px ${rgba(theme('colors.blue.300'), 0.45)}`
			}),
			container: {
				center: true,
				padding: {
					default: '1.25rem',
					sm: '2rem',
					lg: '3rem',
					xl: '12rem',
					xxl: '11rem'
				}
			},
			screens: {
				xxl: '1440px'
			}
		}
	},
	variants: {},
	plugins: [require('@tailwindcss/ui')]
};
