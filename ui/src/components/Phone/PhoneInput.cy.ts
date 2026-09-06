import PhoneInput from './Phone.vue'

function stubTimezone(timeZone: string) {
  cy.stub(Intl.DateTimeFormat.prototype, 'resolvedOptions').returns({
    timeZone,
  } as Intl.ResolvedDateTimeFormatOptions)
}

describe('PhoneInput', () => {
  it('typing emits the joined "<isd>-<number>" format, empty number emits ""', () => {
    stubTimezone('Asia/Kolkata')
    cy.mount(PhoneInput, {
      props: {
        'onUpdate:modelValue': cy.spy().as('onUpdate'),
      },
    })

    cy.get('input[type=tel]').type('9876543210')
    cy.get('@onUpdate').should('have.been.calledWith', '+91-9876543210')

    cy.get('input[type=tel]').clear()
    cy.get('@onUpdate').should('have.been.calledWith', '')
  })

  it('values carrying an ISD re-route through the parser', () => {
    stubTimezone('Asia/Kolkata')
    cy.mount(PhoneInput, {
      props: {
        'onUpdate:modelValue': cy.spy().as('onUpdate'),
      },
    })

    // Typed: "+81" flips the country, the rest stays in the input.
    cy.get('input[type=tel]').type('+819012345678')
    cy.get('[data-slot="country"]').should(
      'have.attr',
      'aria-label',
      'Country: Japan',
    )
    cy.get('input[type=tel]').should('have.value', '9012345678')
    cy.get('@onUpdate').should('have.been.calledWith', '+81-9012345678')

    // Pasted in one go: the longest ISD wins — Bahamas (+1242), not +1.
    cy.get('input[type=tel]').clear().invoke('val', '+12425550100')
    cy.get('input[type=tel]').trigger('input')
    cy.get('[data-slot="country"]').should(
      'have.attr',
      'aria-label',
      'Country: Bahamas',
    )
    cy.get('@onUpdate').should('have.been.calledWith', '+1242-5550100')
  })

  it('external model values parse into country + number without echoing back', () => {
    cy.mount(PhoneInput, {
      props: {
        modelValue: '+91-9876543210',
        'onUpdate:modelValue': cy.spy().as('onUpdate'),
      },
    })

    cy.get('[data-slot="country"]').should(
      'have.attr',
      'aria-label',
      'Country: India',
    )
    cy.contains('+91').should('exist')
    cy.get('input[type=tel]').should('have.value', '9876543210')

    cy.then(() => {
      Cypress.vueWrapper.setProps({ modelValue: '+81-9012345678' })
    })
    cy.get('[data-slot="country"]').should(
      'have.attr',
      'aria-label',
      'Country: Japan',
    )
    cy.get('input[type=tel]').should('have.value', '9012345678')

    // Echo guard: parsing a model update never re-emits it.
    cy.get('@onUpdate').should('not.have.been.called')
  })

  it('picking a country from the dropdown re-emits and focuses the number input', () => {
    stubTimezone('Asia/Kolkata')
    cy.mount(PhoneInput, {
      props: {
        'onUpdate:modelValue': cy.spy().as('onUpdate'),
      },
    })

    cy.get('input[type=tel]').type('9876543210')
    cy.get('[data-slot="country"]').click()
    cy.get('input[placeholder="Search country"]').type('japan')
    cy.get('[role="option"]').should('have.length', 1).click()

    cy.get('[data-slot="country"]').should(
      'have.attr',
      'aria-label',
      'Country: Japan',
    )
    cy.get('@onUpdate').should('have.been.calledWith', '+81-9876543210')
    cy.get('input[type=tel]').should('have.focus')
  })

  it('guesses the country from the system timezone', () => {
    stubTimezone('Asia/Tokyo')
    cy.mount(PhoneInput)
    cy.get('[data-slot="country"]').should(
      'have.attr',
      'aria-label',
      'Country: Japan',
    )
  })

  it('renders no country and the globe placeholder for an unknown timezone', () => {
    stubTimezone('Etc/UTC')
    cy.mount(PhoneInput)
    cy.get('[data-slot="country"]')
      .should('have.attr', 'aria-label', 'Select country')
      .find('.lucide-globe')
      .should('exist')
  })

  it('backspace on an empty number clears the country', () => {
    stubTimezone('Asia/Kolkata')
    cy.mount(PhoneInput)
    cy.get('input[type=tel]').type('{backspace}')
    cy.get('[data-slot="country"]')
      .should('have.attr', 'aria-label', 'Select country')
      .find('.lucide-globe')
      .should('exist')
  })

  it('disabled blocks both the picker and the input', () => {
    cy.mount(PhoneInput, {
      props: { disabled: true, modelValue: '+91-9876543210' },
    })

    cy.get('input[type=tel]').should('be.disabled')
    cy.get('[data-slot="country"]').should('be.disabled')
    cy.get('[data-slot="country"]').click({ force: true })
    cy.get('[role="option"]').should('not.exist')
    cy.get('[data-slot="phone-input"]').should(
      'have.attr',
      'data-disabled',
      'true',
    )
  })

  it('selects a country by keyboard and closes on Escape', () => {
    stubTimezone('Asia/Kolkata')
    cy.mount(PhoneInput)

    // Filter to one match, then Enter commits the highlighted row.
    cy.get('[data-slot="country"]').click()
    cy.get('input[placeholder="Search country"]').type('japan')
    cy.get('[role="option"]').should('have.length', 1)
    cy.get('input[placeholder="Search country"]').type('{downArrow}{enter}')
    cy.get('[data-slot="country"]').should(
      'have.attr',
      'aria-label',
      'Country: Japan',
    )

    // Escape closes the popover without changing the selection.
    cy.get('[data-slot="country"]').click()
    cy.get('[role="option"]').should('have.length.greaterThan', 1)
    cy.get('input[placeholder="Search country"]').type('{esc}')
    cy.get('[role="option"]').should('not.exist')
    cy.get('[data-slot="country"]').should(
      'have.attr',
      'aria-label',
      'Country: Japan',
    )
  })

  it('filters by dial code and renders the empty state', () => {
    stubTimezone('Asia/Kolkata')
    cy.mount(PhoneInput)
    cy.get('[data-slot="country"]').click()

    // The ISD is embedded in each option label, so a dial-code query matches.
    cy.get('input[placeholder="Search country"]').type('+44')
    cy.get('[role="option"]').should('contain.text', 'United Kingdom')

    // No match falls back to the empty-state copy.
    cy.get('input[placeholder="Search country"]').clear().type('zzzzz')
    cy.get('[role="option"]').should('not.exist')
    cy.contains('No country found').should('exist')
  })

  it('honors an explicit id over the generated one', () => {
    cy.mount(PhoneInput, { props: { id: 'phone-x', label: 'Phone' } })
    cy.get('input[type=tel]').should('have.attr', 'id', 'phone-x')
    cy.get('label[for="phone-x"]').should('contain.text', 'Phone')
  })

  it('reflects each size and variant on the shell', () => {
    for (const size of ['sm', 'md', 'lg', 'xl'] as const) {
      cy.mount(PhoneInput, { props: { size } })
      cy.get('[data-slot="phone-input"]').should('have.attr', 'data-size', size)
    }
    for (const variant of ['subtle', 'outline'] as const) {
      cy.mount(PhoneInput, { props: { variant } })
      cy.get('[data-slot="phone-input"]').should(
        'have.attr',
        'data-variant',
        variant,
      )
    }
  })

  describe('shared labeling contract', () => {
    it('renders label and links it to the input via for/id', () => {
      cy.mount(PhoneInput, { props: { label: 'Phone' } })
      cy.get('input[type=tel]').then(($input) => {
        const id = $input.attr('id')!
        cy.get(`label[for="${id}"]`).should('contain.text', 'Phone')
      })
    })

    it('renders description and wires aria-describedby on the input', () => {
      cy.mount(PhoneInput, {
        props: { label: 'Phone', description: 'We will text a code.' },
      })
      cy.get('input[type=tel]').then(($input) => {
        const id = $input.attr('id')!
        expect($input.attr('aria-describedby')).to.equal(`${id}-description`)
        cy.get(`#${id}-description`).should(
          'contain.text',
          'We will text a code.',
        )
      })
    })

    it('renders error with aria-invalid + aria-errormessage and suppresses description', () => {
      cy.mount(PhoneInput, {
        props: { label: 'Phone', description: 'helper', error: 'Required' },
      })
      cy.get('input[type=tel]')
        .should('have.attr', 'aria-invalid', 'true')
        .then(($input) => {
          const id = $input.attr('id')!
          expect($input.attr('aria-errormessage')).to.equal(`${id}-error`)
          cy.get(`#${id}-error`).should('contain.text', 'Required')
          cy.get(`#${id}-description`).should('not.exist')
        })
    })

    it('renders the required indicator and forwards aria-required', () => {
      cy.mount(PhoneInput, { props: { label: 'Phone', required: true } })
      cy.get('input[type=tel]').should('have.attr', 'aria-required', 'true')
      cy.contains('label', 'Phone').within(() => {
        cy.get('span[aria-hidden="true"]').should('contain.text', '*')
      })
    })
  })
})
