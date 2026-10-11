package ru.itmo.talkmate

import org.junit.Assert.assertEquals
import org.junit.Test
import ru.itmo.talkmate.ui.Markup
import ru.itmo.talkmate.ui.Markup.Segment

class MarkupTest {
    @Test
    fun plainTextIsOneSegment() = assertEquals(listOf(Segment("просто текст", false)), Markup.parse("просто текст"))

    @Test
    fun boldInTheMiddle() = assertEquals(
        listOf(Segment("попробуйте ", false), Segment("увеличить громкость", true), Segment(" голоса", false)),
        Markup.parse("попробуйте **увеличить громкость** голоса"),
    )

    @Test
    fun boldAtStartAndEnd() = assertEquals(
        listOf(Segment("раз", true), Segment(" и ", false), Segment("два", true)),
        Markup.parse("**раз** и **два**"),
    )

    @Test
    fun unpairedMarkerKeepsTextAsIs() =
        assertEquals(listOf(Segment("цена 2**3 рубля", false)), Markup.parse("цена 2**3 рубля"))

    @Test
    fun plainStripsMarkers() = assertEquals("а б в", Markup.plain("а **б** в"))

    @Test
    fun emptyString() = assertEquals(emptyList<Segment>(), Markup.parse(""))
}
